"""Dissolved oxygen (DO) mass-balance ODE subsystem.

dDO/dt = (k_L·a/H)·(DO_sat − DO) + P(t) − R_algae − R_shrimp − SOD/H − R_nitr

Reaeration uses Boyd & Teichert-Coddington (1992) wind model plus aerator
contribution, both temperature-corrected via Arrhenius θ=1.024.
DO saturation via Weiss (1970) with salinity correction.

References:
    Boyd, C.E. & Teichert-Coddington, D. (1992). Relationship between KLa and
        wind speed in small aquaculture ponds. Aquacultural Engineering, 11, 121-131.
    Weiss, R.F. (1970). The solubility of nitrogen, oxygen and argon in water and
        seawater. Deep-Sea Research, 17, 721-735.
    Bowie, G.L. et al. (1985). Rates, constants, and kinetics formulations in surface
        water quality modeling. EPA/600/3-85/040.
    O'Connor, D.J. & Dobbins, W.E. (1958). Mechanism of reaeration in natural streams.
        ASCE Trans., 123, 641-684.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from xoceania_sim.forcing.forcing import ForcingState


@dataclass
class DOParams:
    """Parameters for dissolved oxygen dynamics.

    Args:
        depth_m: Pond depth H (m).
        salinity_ppt: Salinity (ppt) for DO saturation correction.
        n_aerators: Number of paddlewheel aerators.
        aerator_kLa_20: Reaeration coefficient per aerator at 20°C (h⁻¹).
            Boyd (1979): paddlewheel 2 kW gives ~1.4 mg O2/L/h in typical pond.
        aeration_fraction: Fraction of aerators currently operating (0-1).
        reaeration_theta: Temperature coefficient. Bowie et al. (1985): θ = 1.024.
        wind_kLa_coef: Boyd & Teichert-Coddington (1992): KLa₂₀ = coef·U − offset.
        wind_kLa_offset: See wind_kLa_coef.
        sod_g_m2_d: Sediment oxygen demand (g O₂/m²/day).
        sod_theta: SOD temperature coefficient. Bowie et al. (1985): θ = 1.065.
        nitr_oxygen_ratio: O₂ consumed per g N nitrified. 4.57 g O₂/g N.
        p_gO2_per_mgChla: Photosynthesis: g O₂ produced per mg Chl-a per unit light.
            Calibrated so peak daytime P ≈ 5-8 mg/L/h in hypereutrophic ponds.
            Actually computed from phytoplankton module; this is a fallback scale.
    """

    depth_m: float = 1.5
    salinity_ppt: float = 15.0
    n_aerators: int = 2
    aerator_kLa_20: float = 0.8
    aeration_fraction: float = 1.0
    reaeration_theta: float = 1.024
    wind_kLa_coef: float = 0.017
    wind_kLa_offset: float = 0.014
    sod_g_m2_d: float = 2.0
    sod_theta: float = 1.065
    nitr_oxygen_ratio: float = 4.57

    @classmethod
    def from_config(cls, cfg: object, aeration_fraction: float = 1.0) -> "DOParams":
        """Construct from PondConfig."""
        return cls(
            depth_m=cfg.depth_m,
            salinity_ppt=cfg.salinity_ppt,
            n_aerators=cfg.n_aerators,
            aerator_kLa_20=cfg.aerator_kLa_20,
            aeration_fraction=aeration_fraction,
            wind_kLa_coef=cfg.wind_reaeration_coef,
            wind_kLa_offset=cfg.wind_reaeration_offset,
            reaeration_theta=cfg.reaeration_theta,
            sod_g_m2_d=cfg.sod_g_m2_d,
            sod_theta=cfg.sod_theta,
        )


def do_saturation(T_C: float, salinity_ppt: float = 0.0) -> float:
    """Dissolved oxygen saturation concentration (mg/L).

    Uses Weiss (1970) empirical equation with Benson & Krause salinity correction.
    Valid for 0-40°C, 0-40 ppt.

    Args:
        T_C: Water temperature (°C).
        salinity_ppt: Salinity (ppt, g/kg).

    Returns:
        DO saturation concentration (mg/L).

    References:
        Weiss, R.F. (1970). Deep-Sea Research, 17, 721-735.
        Benson, B.B. & Krause, D. (1984). Limnol. Oceanogr., 29, 620-632.
    """
    T_K = T_C + 273.15
    # Weiss (1970) coefficients for freshwater
    ln_DO = (
        -139.34411
        + 157570.1 / T_K
        - 66423080.0 / T_K**2
        + 12438.25e6 / T_K**3
        - 862194900000.0 / T_K**4
    )
    DO_fresh = math.exp(ln_DO)

    # Salinity correction: Benson & Krause (1984) / Garcia & Gordon (1992)
    # ΔlnDO = S × (−0.017674 + 10.754/T_K − 2140.7/T_K²)
    if salinity_ppt > 0.0:
        ln_DO_s = salinity_ppt * (
            -0.017674 + 10.754 / T_K - 2140.7 / T_K**2
        )
        return DO_fresh * math.exp(ln_DO_s)
    return DO_fresh


def _reaeration_rate(
    T_C: float,
    u_wind_ms: float,
    params: DOParams,
) -> float:
    """Total reaeration rate k_L·a (h⁻¹) at temperature T_C.

    Combines wind-driven reaeration (Boyd & Teichert-Coddington 1992) and
    mechanical aerator contribution, both temperature-corrected.

    Args:
        T_C: Water temperature (°C).
        u_wind_ms: Wind speed at 3 m (m/s).
        params: DOParams.

    Returns:
        k_L·a in h⁻¹.
    """
    # Wind reaeration: KLa₂₀ = coef·U − offset, minimum 0
    kLa_wind_20 = max(0.0, params.wind_kLa_coef * u_wind_ms - params.wind_kLa_offset)

    # Aerator contribution
    kLa_aer_20 = params.n_aerators * params.aerator_kLa_20 * params.aeration_fraction

    kLa_20 = kLa_wind_20 + kLa_aer_20

    # Arrhenius temperature correction (θ = 1.024)
    return kLa_20 * params.reaeration_theta ** (T_C - 20.0)


def dDO_dt(
    DO: float,
    T_C: float,
    forcing: ForcingState,
    params: DOParams,
    P_gross: float,
    R_algae: float,
    R_shrimp: float,
    R_nitr: float,
) -> float:
    """Rate of change of dissolved oxygen (mg/L/h).

    Complete mass-balance equation:
        dDO/dt = k_L·a·(DO_sat − DO)/H + P_gross − R_algae − R_shrimp
                 − SOD/H − 4.57·R_nitr

    Args:
        DO: Current DO concentration (mg/L).
        T_C: Water temperature (°C).
        forcing: ForcingState with wind speed.
        params: DOParams.
        P_gross: Gross photosynthetic O₂ production (mg/L/h).
        R_algae: Algal dark respiration O₂ demand (mg/L/h).
        R_shrimp: Shrimp O₂ demand (mg/L/h).
        R_nitr: Nitrification O₂ demand (mg N/L/h, converted internally by 4.57).

    Returns:
        dDO/dt in mg/L/h.

    References:
        Boyd & Teichert-Coddington (1992). Aquacultural Engineering, 11, 121-131.
        Bowie et al. (1985). EPA/600/3-85/040.
    """
    DO_sat = do_saturation(T_C, params.salinity_ppt)
    kLa = _reaeration_rate(T_C, forcing.u_wind, params)

    # Reaeration (positive when DO < DO_sat)
    R_reaer = kLa * (DO_sat - DO)

    # SOD: convert g/m²/day to mg/L/h, temperature corrected
    # SOD_T (g/m²/day) × 1000 mg/g ÷ depth(m) ÷ 1000 L/m³ × 1000 mg/g / 24 h
    # = SOD_T [g/m²/d] * 1000 [mg/g] / depth [m] / 1000 [L/m³] / 24 [h/d]
    # = SOD_T / depth / 24   (g/m²/d → g/m³/h → g/1000L/h → mg/L/h * 1000/1000 = 1)
    # Correct: 2 g/m²/d ÷ 1.5 m ÷ 24 h = 0.0556 g/m³/h = 55.6 mg/m³/h = 0.0556 mg/L/h
    # BUT: 1 m³ = 1000 L, so g/m³ = mg/L / 1000 → 0.0556 mg/L/h ... still wrong.
    # g/m²/d ÷ depth [m] = g/m³/d, then g/m³ = 1000 mg/m³ = 1 mg/L
    # So: 2 g/m²/d ÷ 1.5 m = 1.33 g/m³/d = 1333 mg/m³/d ÷ 24 h = 55.6 mg/m³/h = 0.0556 mg/L ... no
    # Actually: 1 g/m³ = 1 mg/L (water). So 1333 mg/m³ = 1.333 mg/L, /24h = 0.0556 mg/L/h
    # CORRECT formula: SOD (g/m²/d) * 1000 (mg/g) / depth (m) / 1000 (L/m³) / 24 (h/d) [mg/L/h]
    # = SOD / depth / 24 / 1   ... wait: 2 * 1000 / 1.5 / 1000 / 24 = 2/1.5/24 = 0.0556 mg/L/h
    sod_T = params.sod_g_m2_d * params.sod_theta ** (T_C - 20.0)
    R_sod = sod_T / params.depth_m / 24.0  # mg/L/h (g/m²/d * 1000mg/g / 1000L/m³ / depth / 24h = /depth/24)

    # Nitrification O₂ demand: 4.57 g O₂ per g N nitrified
    R_nitr_o2 = params.nitr_oxygen_ratio * R_nitr  # mg/L/h

    dDO = R_reaer + P_gross - R_algae - R_shrimp - R_sod - R_nitr_o2
    return dDO
