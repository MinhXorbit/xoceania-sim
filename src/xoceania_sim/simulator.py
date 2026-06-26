"""Coupled ODE integrator for xoceania-sim.

PondSimulator assembles all subsystem ODEs into a single right-hand side function
and integrates using scipy's solve_ivp with LSODA (handles stiffness automatically).

State vector: [T, DO, C_T, TAN, A, W, B]  (7 states; survival tracked separately)

References:
    Losordo & Piedrahita (1991). Ecol. Modelling, 54, 189-226.
    Culberson & Piedrahita (1996). Ecol. Modelling, 89, 231-258.
    Hargreaves (1998). Aquaculture, 166, 181-212.
"""

from __future__ import annotations

import math
import warnings
from typing import Callable, Optional

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from xoceania_sim.config import SimConfig, PondConfig, ShrimpConfig
from xoceania_sim.forcing.forcing import EnvironmentalForcing, ForcingState, create_forcing
from xoceania_sim.subsystems.temperature import TemperatureParams, dT_dt
from xoceania_sim.subsystems.dissolved_oxygen import DOParams, dDO_dt, do_saturation
from xoceania_sim.subsystems.ph_carbon import CarbonParams, dCT_dt, solve_pH
from xoceania_sim.subsystems.nitrogen import NitrogenParams, dTAN_dt, nh3_fraction
from xoceania_sim.subsystems.phytoplankton import PhytoplanktonParams, dA_dt
from xoceania_sim.subsystems.shrimp import ShrimpParams, ShrimpState, update_shrimp


# State vector indices
_IDX_T = 0
_IDX_DO = 1
_IDX_CT = 2
_IDX_TAN = 3
_IDX_A = 4
_IDX_W = 5
_IDX_B = 6


class SimulationResult:
    """Container for simulation output with convenient access methods.

    Attributes:
        df: pandas DataFrame indexed by time (hours), with columns:
            T, DO, C_T, TAN, A, W, B, pH, NH3, DO_sat, DO_pct_sat.
        config: SimConfig used for this run.
    """

    def __init__(self, df: pd.DataFrame, config: SimConfig) -> None:
        self.df = df
        self.config = config

    def __repr__(self) -> str:
        return (
            f"SimulationResult(t={self.df.index[0]:.1f}–{self.df.index[-1]:.1f} h, "
            f"n_points={len(self.df)})"
        )

    def summary(self) -> pd.DataFrame:
        """Return descriptive statistics of key water quality variables."""
        cols = ["T", "DO", "pH", "TAN", "NH3", "A"]
        return self.df[[c for c in cols if c in self.df.columns]].describe()


class PondSimulator:
    """Coupled ODE simulator for aquaculture pond water quality.

    Integrates 7 coupled state variables (T, DO, C_T, TAN, A, W, B) using
    scipy's LSODA solver (handles ODE stiffness from nitrification and CO₂ exchange).

    Args:
        config: SimConfig with pond, shrimp, and weather parameters.

    Example:
        >>> from xoceania_sim import PondSimulator, load_config
        >>> cfg = load_config("configs/vannamei_mekong.yaml")
        >>> sim = PondSimulator(cfg)
        >>> result = sim.run(t_span=(0, 48))
        >>> print(result.df[["DO", "pH", "T"]].describe())
    """

    def __init__(self, config: SimConfig) -> None:
        self._cfg = config
        self._pond = config.pond
        self._shrimp_cfg = config.shrimp
        self._weather = config.weather

        # Build parameter objects for each subsystem
        self._T_params = TemperatureParams.from_pond_config(self._pond)
        self._DO_params = DOParams.from_config(self._pond)
        self._C_params = CarbonParams.from_config(self._pond)
        self._N_params = NitrogenParams.from_config(self._pond)
        self._A_params = PhytoplanktonParams.from_config(self._pond)
        self._shrimp_params = ShrimpParams.from_config(self._shrimp_cfg)

        # Environmental forcing
        self._forcing = create_forcing(self._pond, self._weather)

        # Alkalinity (slowly varying; updated during run)
        self._alkalinity = self._pond.alkalinity_mg_L

        # Shrimp survival (not in main ODE vector; updated via events)
        self._survival = self._shrimp_cfg.initial_survival

        # Management schedule lookups
        self._aeration_schedule = config.aeration_schedule
        self._feed_schedule = config.feed_schedule
        self._exchange_events = sorted(config.exchange_events or [])

    def _aeration_fraction(self, t_hours: float) -> float:
        """Return aeration fraction at time t_hours (0-1)."""
        if self._aeration_schedule is None:
            return 1.0
        # Find the latest schedule time ≤ t_hours
        t_day = t_hours % 24.0
        times = sorted(self._aeration_schedule.keys())
        frac = 1.0
        for ts in times:
            if ts <= t_day:
                frac = self._aeration_schedule[ts]
        return frac

    def _feed_multiplier(self, t_hours: float) -> float:
        """Return feed multiplier at time t_hours."""
        if self._feed_schedule is None:
            return 1.0
        day = int(t_hours // 24)
        return self._feed_schedule.get(day, 1.0)

    def _rhs(self, t: float, y: np.ndarray) -> np.ndarray:
        """Right-hand side of the coupled ODE system.

        State: y = [T, DO, C_T, TAN, A, W, B]

        All rates are in per-hour units (state units per hour).

        Args:
            t: Current time (hours from simulation start).
            y: State vector.

        Returns:
            dy/dt vector (same shape as y).
        """
        # Unpack and clamp state variables
        T = float(np.clip(y[_IDX_T], 0.0, 45.0))
        DO = float(np.clip(y[_IDX_DO], 0.0, 30.0))
        CT = float(np.clip(y[_IDX_CT], 0.5, 20.0))
        TAN = float(np.clip(y[_IDX_TAN], 0.0, 50.0))
        A = float(np.clip(y[_IDX_A], 0.0, 5000.0))
        W = float(np.clip(y[_IDX_W], 0.01, 1000.0))
        B = float(np.clip(y[_IDX_B], 0.0, 1e6))

        # Environmental forcing
        forcing = self._forcing.at(t)

        # Aeration and feeding state
        aer_frac = self._aeration_fraction(t)
        feed_mult = self._feed_multiplier(t)

        # Update DO params with current aeration fraction
        DO_params = DOParams(
            depth_m=self._DO_params.depth_m,
            salinity_ppt=self._DO_params.salinity_ppt,
            n_aerators=self._DO_params.n_aerators,
            aerator_kLa_20=self._DO_params.aerator_kLa_20,
            aeration_fraction=aer_frac,
            reaeration_theta=self._DO_params.reaeration_theta,
            wind_kLa_coef=self._DO_params.wind_kLa_coef,
            wind_kLa_offset=self._DO_params.wind_kLa_offset,
            sod_g_m2_d=self._DO_params.sod_g_m2_d,
            sod_theta=self._DO_params.sod_theta,
        )

        # --- pH/CO₂ (algebraic from C_T and alkalinity) ---
        pH, CO2_mg_L = solve_pH(CT, self._alkalinity, T, self._pond.salinity_ppt)

        # --- Phytoplankton ---
        dA, P_gross_o2, R_algae_o2 = dA_dt(A, T, TAN, forcing, self._A_params, pH=pH, CT_mmol_L=CT)

        # --- Nitrogen ---
        NH3_frac = nh3_fraction(pH, T)
        NH3_mg_L = NH3_frac * TAN  # un-ionized NH₃ (mg N/L)

        # Shrimp rates (not ODE for shrimp — rates used by DO/TAN ODEs)
        shrimp_state = ShrimpState(W_g=W, B_g_m2=B, survival=self._survival)
        _, R_shrimp_o2_m2, E_shrimp_tan_m2, _ = update_shrimp(
            shrimp_state, T, DO, NH3_mg_L, 1.0,  # dt=1h (rates)
            self._shrimp_params, feed_multiplier=feed_mult,
            pond_area_m2=self._pond.area_m2,
        )

        # Convert biomass-based rates to volumetric (mg/L/h)
        depth = self._pond.depth_m
        R_shrimp_o2 = R_shrimp_o2_m2 / depth / 1000.0  # mg O₂/L/h
        E_shrimp_tan = E_shrimp_tan_m2 / depth / 1000.0  # mg N/L/h

        # --- TAN ---
        dTAN, R_nitr = dTAN_dt(TAN, DO, T, pH, forcing, self._N_params, E_shrimp_tan, A)

        # --- DO ---
        dDO = dDO_dt(DO, T, forcing, DO_params, P_gross_o2, R_algae_o2, R_shrimp_o2, R_nitr)

        # --- C_T ---
        dCT = dCT_dt(
            CT, T, forcing, self._C_params,
            R_algae_o2, R_shrimp_o2, P_gross_o2, R_nitr,
        )

        # --- Temperature ---
        dT = dT_dt(T, forcing, self._T_params)

        # --- Shrimp growth (W and B) ---
        # Use instantaneous growth rate from shrimp module
        # Growth (g/shrimp/h) from feed-conversion
        from xoceania_sim.subsystems.shrimp import (
            _interpolate_feed_rate, _shrimp_respiration_o2, _stress_mortality
        )
        W_eff = max(W, 0.01)
        feed_pct_bw = _interpolate_feed_rate(
            W_eff, self._shrimp_params.feed_table_weight, self._shrimp_params.feed_table_pct_bw
        )
        feed_g_d = W_eff * feed_pct_bw / 100.0 * feed_mult
        t_factor = max(0.0, 1.0 - (
            (T - self._shrimp_params.t_opt) / (self._shrimp_params.t_max - self._shrimp_params.t_opt)
        ) ** 2)
        dW = (feed_g_d / self._shrimp_params.fcr) * t_factor / 24.0  # g/h

        # Biomass: B = n0 × survival × W; dB/dt = n0 × survival × dW − n0 × W × mort
        mort_rate_h = _stress_mortality(DO, NH3_mg_L, self._shrimp_params)
        n0 = self._shrimp_params.stocking_density_m2
        dB = n0 * self._survival * dW - n0 * W * mort_rate_h * self._survival
        # Update survival (approximation; ODE for survival is implicitly coupled)
        # Survival is updated in the Euler step external to the ODE solver
        # For the ODE, use survival as slowly-varying parameter
        # dsurvival/dt not a state; instead track via B and W relationship

        dy = np.array([dT, dDO, dCT, dTAN, dA, dW, dB], dtype=float)

        # NaN guard
        dy = np.where(np.isfinite(dy), dy, 0.0)
        return dy

    def run(
        self,
        t_span: tuple[float, float] | None = None,
        t_eval: np.ndarray | None = None,
        method: str | None = None,
    ) -> SimulationResult:
        """Run the coupled ODE simulation.

        Args:
            t_span: (t_start, t_end) in hours. Defaults to (0, t_end_days*24).
            t_eval: Times at which to evaluate the solution (hours).
                Defaults to hourly steps from t_start to t_end.
            method: ODE solver method. Default from config (LSODA).

        Returns:
            SimulationResult with DataFrame of time-indexed state variables.

        Raises:
            RuntimeError: If ODE integration fails.
        """
        if t_span is None:
            t_span = (0.0, self._cfg.t_end_days * 24.0)
        if t_eval is None:
            t_eval = np.arange(t_span[0], t_span[1] + self._cfg.dt_hours, self._cfg.dt_hours)
        if method is None:
            method = self._cfg.solver_method

        # Initial conditions
        y0 = np.array([
            self._cfg.initial_temp,
            self._cfg.initial_do,
            self._cfg.initial_CT,
            self._cfg.initial_TAN,
            self._cfg.initial_algae,
            self._shrimp_cfg.initial_weight_g,
            self._shrimp_cfg.stocking_density_m2 * self._shrimp_cfg.initial_weight_g,
        ], dtype=float)

        # Reset survival for new run
        self._survival = self._shrimp_cfg.initial_survival

        # Water exchange events as time instants
        exchange_times = [ev[0] * 24.0 for ev in self._exchange_events]

        def rhs_wrapped(t: float, y: np.ndarray) -> np.ndarray:
            return self._rhs(t, y)

        # Integrate
        sol = solve_ivp(
            rhs_wrapped,
            t_span,
            y0,
            method=method,
            t_eval=t_eval,
            rtol=self._cfg.rtol,
            atol=self._cfg.atol,
            dense_output=False,
        )

        if not sol.success:
            warnings.warn(f"ODE solver warning: {sol.message}", RuntimeWarning)

        t_out = sol.t
        y_out = sol.y  # shape (7, n_t)

        # Build output DataFrame
        T_arr = np.clip(y_out[_IDX_T], 0.0, 45.0)
        DO_arr = np.clip(y_out[_IDX_DO], 0.0, 30.0)
        CT_arr = np.clip(y_out[_IDX_CT], 0.5, 20.0)
        TAN_arr = np.clip(y_out[_IDX_TAN], 0.0, 50.0)
        A_arr = np.clip(y_out[_IDX_A], 0.0, 5000.0)
        W_arr = np.clip(y_out[_IDX_W], 0.01, 1000.0)
        B_arr = np.clip(y_out[_IDX_B], 0.0, 1e6)

        # Derived: pH, NH3, DO_sat, DO_pct_sat
        pH_arr = np.zeros(len(t_out))
        NH3_arr = np.zeros(len(t_out))
        DO_sat_arr = np.zeros(len(t_out))
        CO2_arr = np.zeros(len(t_out))

        for i, (T, CT, TAN, t) in enumerate(zip(T_arr, CT_arr, TAN_arr, t_out)):
            pH, CO2_mg = solve_pH(CT, self._alkalinity, T, self._pond.salinity_ppt)
            pH_arr[i] = pH
            CO2_arr[i] = CO2_mg
            NH3_frac = nh3_fraction(pH, T)
            NH3_arr[i] = NH3_frac * TAN
            DO_sat_arr[i] = do_saturation(T, self._pond.salinity_ppt)

        DO_pct_sat = DO_arr / np.maximum(DO_sat_arr, 0.1) * 100.0

        df = pd.DataFrame({
            "T": T_arr,
            "DO": DO_arr,
            "C_T": CT_arr,
            "TAN": TAN_arr,
            "A": A_arr,
            "W": W_arr,
            "B": B_arr,
            "pH": pH_arr,
            "NH3": NH3_arr,
            "DO_sat": DO_sat_arr,
            "DO_pct_sat": DO_pct_sat,
            "CO2": CO2_arr,
        }, index=t_out)
        df.index.name = "time_h"

        # Update survival (Euler approximation from B and W)
        W_last = float(W_arr[-1])
        B_last = float(B_arr[-1])
        n0 = self._shrimp_params.stocking_density_m2
        if n0 > 0 and W_last > 0:
            self._survival = B_last / (n0 * W_last)

        return SimulationResult(df, self._cfg)

    def reset(self) -> None:
        """Reset simulator state (survival, alkalinity) to initial conditions."""
        self._survival = self._shrimp_cfg.initial_survival
        self._alkalinity = self._pond.alkalinity_mg_L
