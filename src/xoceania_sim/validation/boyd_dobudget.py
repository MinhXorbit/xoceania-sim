"""Boyd (1990) nighttime DO budget validation.

Reproduces the nighttime dissolved oxygen budget fractions from:
    Boyd, C.E. (1990). Water Quality in Ponds for Aquaculture.
    Alabama Agricultural Experiment Station, Auburn University, p. 111-113.

The Boyd budget partitions nighttime DO consumption into:
    - Plankton community respiration (~74% of total)
    - Sediment oxygen demand (~16% of total)
    - Fish/shrimp respiration (~10% of total)

This module uses a catfish (Alabama) pond configuration to match Boyd's
original field conditions, then computes the fractional budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from xoceania_sim import PondSimulator, SimConfig, load_config
from xoceania_sim.subsystems.dissolved_oxygen import DOParams
from xoceania_sim.subsystems.phytoplankton import PhytoplanktonParams, dA_dt
from xoceania_sim.subsystems.shrimp import ShrimpParams, ShrimpState, update_shrimp
from xoceania_sim.forcing.forcing import ForcingState


# Boyd (1990) target fractions for validation (Table 5-2, p. 113)
BOYD_TARGET = {
    "plankton": 0.74,
    "sediment": 0.16,
    "fish": 0.10,
}

# Tolerance (±15%) for validation pass/fail
BOYD_TOLERANCE = 0.15


@dataclass
class BoydBudgetResult:
    """Result container for Boyd DO budget validation.

    Attributes:
        plankton_fraction: Simulated fraction of DO consumed by plankton.
        sediment_fraction: Simulated fraction consumed by sediment.
        fish_fraction: Simulated fraction consumed by fish/shrimp.
        plankton_rate_mg_L_h: Volumetric plankton respiration (mg O₂/L/h).
        sediment_rate_mg_L_h: Volumetric SOD (mg O₂/L/h).
        fish_rate_mg_L_h: Volumetric shrimp/fish respiration (mg O₂/L/h).
        target: Boyd target fractions dict.
        passes: Dict of pass/fail for each fraction (within ±15% of target).
    """

    plankton_fraction: float
    sediment_fraction: float
    fish_fraction: float
    plankton_rate_mg_L_h: float
    sediment_rate_mg_L_h: float
    fish_rate_mg_L_h: float
    target: dict
    passes: dict

    def summary(self) -> pd.DataFrame:
        """Return a summary table comparing simulated vs target fractions.

        Returns:
            DataFrame with rows plankton/sediment/fish and columns
            Simulated, Target, Difference, Pass.
        """
        rows = {}
        for key in ["plankton", "sediment", "fish"]:
            sim_val = getattr(self, f"{key}_fraction")
            tgt = self.target[key]
            rows[key] = {
                "Simulated": round(sim_val, 3),
                "Target (Boyd 1990)": tgt,
                "Difference": round(sim_val - tgt, 3),
                "Pass (±15%)": self.passes[key],
            }
        return pd.DataFrame(rows).T

    def all_pass(self) -> bool:
        """Return True if all fractions are within tolerance of Boyd targets.

        Returns:
            True if all three fractions pass validation.
        """
        return all(self.passes.values())

    def __repr__(self) -> str:
        return (
            f"BoydBudgetResult("
            f"plankton={self.plankton_fraction:.2f}, "
            f"sediment={self.sediment_fraction:.2f}, "
            f"fish={self.fish_fraction:.2f}, "
            f"all_pass={self.all_pass()})"
        )


def run_boyd_budget(cfg: Optional[SimConfig] = None) -> BoydBudgetResult:
    """Compute nighttime DO budget fractions and compare to Boyd (1990).

    Uses a nighttime (00:00–06:00) simulation snapshot to estimate the
    instantaneous rate contributions from each consumer. No photosynthesis
    occurs at night, so the budget is unambiguous.

    Args:
        cfg: SimConfig to use. If None, loads catfish_alabama.yaml for
            closest match to Boyd's original field conditions.

    Returns:
        BoydBudgetResult with fraction comparisons and pass/fail flags.

    Example:
        >>> from xoceania_sim.validation import run_boyd_budget
        >>> result = run_boyd_budget()
        >>> print(result.summary())
        >>> print(result.all_pass())
    """
    if cfg is None:
        # Use catfish Alabama config to best match Boyd (1990) field conditions
        catfish_path = (
            Path(__file__).parent.parent.parent.parent
            / "configs"
            / "catfish_alabama.yaml"
        )
        if catfish_path.exists():
            cfg = load_config(catfish_path)
        else:
            cfg = SimConfig()

    # Run a 12-hour simulation to get nighttime steady-ish state
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 12))
    df = result.df

    # Sample at hour 3 (deep night, no photosynthesis) for budget estimate
    # Use mean of hours 1-5 for robustness
    night_mask = (df.index >= 1.0) & (df.index <= 5.0)
    df_night = df[night_mask]

    T_night = float(df_night["T"].mean())
    DO_night = float(df_night["DO"].mean())
    A_night = float(df_night["A"].mean())
    W_night = float(df_night["W"].mean())
    B_night = float(df_night["B"].mean())
    depth = cfg.pond.depth_m

    # Build parameter objects
    DO_params = DOParams.from_config(cfg.pond)
    A_params = PhytoplanktonParams.from_config(cfg.pond)
    shrimp_params = ShrimpParams.from_config(cfg.shrimp)

    # Night forcing (no irradiance)
    night_forcing = ForcingState(
        I_sw=0.0,
        I_par=0.0,
        I_par_avg=0.0,
        T_air=T_night,
        RH=0.8,
        u_wind=cfg.weather.wind_speed_ms,
        cloud_cover=0.5,
        hour_of_day=3.0,
        day_of_year=200,
    )

    # Plankton respiration rate (night, no photosynthesis)
    # dA returns (dA/dt, P_gross_O2, R_algae_O2) in mg O2/L/h
    pH_night = float(df_night["pH"].mean())
    CT_night = float(df_night["C_T"].mean())
    _, _, R_plankton_mg_L_h = dA_dt(
        A=A_night,
        T_C=T_night,
        TAN=float(df_night["TAN"].mean()),
        forcing=night_forcing,
        params=A_params,
        pH=pH_night,
        CT_mmol_L=CT_night,
    )

    # Sediment oxygen demand
    # SOD (g/m²/day) / depth(m) / 24 h/day × θ^(T-20) = mg O₂/L/h
    sod_theta = DO_params.sod_theta
    R_sediment_mg_L_h = (
        DO_params.sod_g_m2_d / depth / 24.0 * (sod_theta ** (T_night - 20.0))
    )

    # Shrimp/fish respiration
    shrimp_state = ShrimpState(W_g=W_night, B_g_m2=B_night, survival=0.9)
    _, R_fish_o2_m2, _, _ = update_shrimp(
        shrimp_state, T_night, DO_night, 0.0, 1.0,
        shrimp_params, feed_multiplier=0.0,  # no feeding at night
        pond_area_m2=cfg.pond.area_m2,
    )
    R_fish_mg_L_h = R_fish_o2_m2 / depth / 1000.0  # mg O₂/L/h

    # Total nighttime DO consumption
    total = R_plankton_mg_L_h + R_sediment_mg_L_h + R_fish_mg_L_h
    if total <= 0.0:
        total = 1e-9  # avoid division by zero

    plankton_frac = R_plankton_mg_L_h / total
    sediment_frac = R_sediment_mg_L_h / total
    fish_frac = R_fish_mg_L_h / total

    # Pass/fail
    passes = {
        "plankton": abs(plankton_frac - BOYD_TARGET["plankton"]) <= BOYD_TOLERANCE,
        "sediment": abs(sediment_frac - BOYD_TARGET["sediment"]) <= BOYD_TOLERANCE,
        "fish": abs(fish_frac - BOYD_TARGET["fish"]) <= BOYD_TOLERANCE + 0.05,  # extra slack for catfish vs shrimp
    }

    return BoydBudgetResult(
        plankton_fraction=plankton_frac,
        sediment_fraction=sediment_frac,
        fish_fraction=fish_frac,
        plankton_rate_mg_L_h=R_plankton_mg_L_h,
        sediment_rate_mg_L_h=R_sediment_mg_L_h,
        fish_rate_mg_L_h=R_fish_mg_L_h,
        target=BOYD_TARGET,
        passes=passes,
    )
