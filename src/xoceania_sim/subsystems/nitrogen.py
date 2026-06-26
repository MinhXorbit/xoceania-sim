"""Total ammonia nitrogen (TAN) ODE subsystem.

dTAN/dt = E_shrimp + F_min + F_sed − R_nitr − U_algae − V_NH3

Nitrification uses two-step Monod kinetics with DO limitation (Hargreaves 1998).
NH₃ fraction from pH/T equilibrium (Emerson 1975).
Volatilization first-order in [NH₃] unprotonated fraction.

References:
    Hargreaves, J.A. (1998). Nitrogen biogeochemistry of aquaculture ponds.
        Aquaculture, 166, 181-212.
    Emerson, K. et al. (1975). Aqueous ammonia equilibrium calculations: effect
        of pH and temperature. Journal of the Fisheries Research Board of Canada,
        32, 2379-2383.
    Bowie, G.L. et al. (1985). EPA/600/3-85/040.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from xoceania_sim.forcing.forcing import ForcingState


@dataclass
class NitrogenParams:
    """Parameters for TAN/nitrogen dynamics.

    Args:
        depth_m: Pond depth H (m).
        nitr_rate_max: Maximum nitrification rate μ_max_nitr (mg N/L/h).
            Hargreaves (1998): 0.01-0.10 mg N/L/h in warm ponds.
        nitr_half_sat_TAN: Monod half-saturation for TAN in nitrification (mg N/L).
            Hargreaves (1998): K_TAN = 0.5-2.0 mg N/L.
        nitr_half_sat_DO: Monod half-saturation for DO in nitrification (mg/L).
            Hargreaves (1998): K_DO = 0.5-1.0 mg O₂/L.
        nitr_theta: Arrhenius θ for nitrification. Standard: 1.08 (Bowie 1985).
        algae_uptake_rate: TAN uptake by phytoplankton (mg N/mg Chl/h).
            Calibrated to typical eutrophic pond dynamics.
        volatilization_rate: First-order NH₃ volatilization coefficient (h⁻¹).
            Approximate; depends on wind and temperature.
        sediment_TAN_flux: TAN flux from sediment (mg N/m²/day).
            Hargreaves (1998): 5-50 mg N/m²/day for intensive ponds.
        mineralization_frac: Fraction of feed that mineralizes to TAN directly.
    """

    depth_m: float = 1.5
    nitr_rate_max: float = 0.04
    nitr_half_sat_TAN: float = 1.0
    nitr_half_sat_DO: float = 0.5
    nitr_theta: float = 1.08
    algae_uptake_rate: float = 0.002
    volatilization_rate: float = 0.005
    sediment_TAN_flux: float = 5.0   # mg N/m²/day; Hargreaves (1998): 5-20 for intensive ponds
    mineralization_frac: float = 0.05

    @classmethod
    def from_config(cls, cfg: object) -> "NitrogenParams":
        return cls(depth_m=cfg.depth_m)


def nh3_fraction(pH: float, T_C: float) -> float:
    """Fraction of TAN that is un-ionized NH₃.

    f_NH3 = 1 / (1 + 10^(pKa − pH))

    where pKa(T) from Emerson et al. (1975):
        pKa = 0.09018 + 2729.92 / T_K

    Args:
        pH: Water pH.
        T_C: Water temperature (°C).

    Returns:
        Un-ionized NH₃ fraction (dimensionless, 0-1).

    References:
        Emerson, K. et al. (1975). J. Fish. Res. Board Canada, 32, 2379-2383.
    """
    T_K = T_C + 273.15
    pKa = 0.09018 + 2729.92 / T_K
    return 1.0 / (1.0 + 10.0 ** (pKa - pH))


def _nitrification_rate(
    TAN: float,
    DO: float,
    T_C: float,
    params: NitrogenParams,
) -> float:
    """Monod dual-substrate nitrification rate (mg N/L/h).

    R_nitr = μ_max · (TAN/(K_TAN + TAN)) · (DO/(K_DO + DO)) · θ^(T-20)

    Nitrification is inhibited at low DO (K_DO = 0.5 mg/L). At DO < 1 mg/L,
    nitrification essentially ceases (anaerobic conditions).

    Args:
        TAN: Total ammonia nitrogen (mg N/L).
        DO: Dissolved oxygen (mg/L).
        T_C: Temperature (°C).
        params: NitrogenParams.

    Returns:
        Nitrification rate (mg N/L/h).

    References:
        Hargreaves (1998). Aquaculture, 166, 181-212.
        Bowie et al. (1985). EPA/600/3-85/040.
    """
    if TAN <= 0.0 or DO <= 0.0:
        return 0.0
    monod_TAN = TAN / (params.nitr_half_sat_TAN + TAN)
    monod_DO = DO / (params.nitr_half_sat_DO + DO)
    theta_corr = params.nitr_theta ** (T_C - 20.0)
    return params.nitr_rate_max * monod_TAN * monod_DO * theta_corr


def dTAN_dt(
    TAN: float,
    DO: float,
    T_C: float,
    pH: float,
    forcing: ForcingState,
    params: NitrogenParams,
    E_shrimp: float,
    A_chl: float,
) -> tuple[float, float]:
    """Rate of change of total ammonia nitrogen (mg N/L/h).

    dTAN/dt = E_shrimp + F_sed − R_nitr − U_algae − V_NH3

    Where:
        E_shrimp: Shrimp TAN excretion (mg N/L/h).
        F_sed: Sediment TAN flux normalized by depth.
        R_nitr: Monod nitrification (mg N/L/h).
        U_algae: Algal TAN uptake (mg N/L/h).
        V_NH3: NH₃ volatilization (mg N/L/h).

    Args:
        TAN: Total ammonia nitrogen (mg N/L).
        DO: Dissolved oxygen (mg/L).
        T_C: Water temperature (°C).
        pH: Water pH (used for NH₃ fraction).
        forcing: ForcingState.
        params: NitrogenParams.
        E_shrimp: Shrimp TAN excretion rate (mg N/L/h).
        A_chl: Phytoplankton chlorophyll-a (mg/m³ = μg/L).

    Returns:
        Tuple of (dTAN/dt, R_nitr) in mg N/L/h.

    References:
        Hargreaves (1998). Aquaculture, 166, 181-212.
        Emerson et al. (1975). J. Fish. Res. Board Canada, 32, 2379-2383.
    """
    # Sediment TAN flux: mg N/m²/day → mg N/L/h
    F_sed = params.sediment_TAN_flux / params.depth_m / 24.0  # mg N/L/h

    # Nitrification
    R_nitr = _nitrification_rate(TAN, DO, T_C, params)

    # Algal TAN uptake (Monod on TAN, light-limited proportional to A)
    # U = uptake_rate * A_chl * TAN/(K_N + TAN)
    K_N = 0.1  # mg N/L half-saturation for algal uptake
    U_algae = params.algae_uptake_rate * max(0.0, A_chl) * TAN / (K_N + TAN + 1e-12)

    # NH3 volatilization: V = k_v * f_NH3 * TAN
    f_nh3 = nh3_fraction(pH, T_C)
    V_NH3 = params.volatilization_rate * f_nh3 * TAN

    # Ensure TAN doesn't go negative
    TAN_eff = max(TAN, 0.0)
    dTAN = E_shrimp + F_sed - R_nitr - U_algae - V_NH3

    return dTAN, R_nitr
