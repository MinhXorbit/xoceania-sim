"""Penaeus vannamei shrimp biomass, growth, and respiration module.

State: mean body weight W (g), total biomass B (g/m²), survival fraction s.

Respiration: VO2 = a · W^b · θ^(T-20) · f(DO)
Excretion: TAN = 0.025 × feed_rate
Growth: feed-conversion model with FCR = 1.5
Mortality: stress-dependent on DO and un-ionized NH₃

References:
    Rosas, C. et al. (2001). Respiration of Penaeus vannamei.
        Aquaculture, 195, 277-289.
    Martínez-Córdova, L.R. et al. (2009). Aquaculture of Penaeus vannamei.
        Aquacultural Engineering, 40, 159-164.
    Boyd, C.E. & Tucker, C.S. (1998). Pond Aquaculture Water Quality Management.
    Hargreaves, J.A. (1998). Nitrogen biogeochemistry of aquaculture ponds.
        Aquaculture, 166, 181-212.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ShrimpState:
    """Current state of the shrimp population.

    Attributes:
        W_g: Mean individual body weight (g).
        B_g_m2: Total biomass per unit area (g/m²).
        survival: Survival fraction (0-1). Initial = 1.0.
    """

    W_g: float = 1.0
    B_g_m2: float = 100.0   # stocking density × initial weight (g/m²)
    survival: float = 1.0


@dataclass
class ShrimpParams:
    """Parameters for the Penaeus vannamei shrimp module.

    Args:
        stocking_density_m2: Initial stocking density (PL/m²).
        fcr: Feed conversion ratio (g feed / g wet weight gain).
        resp_a: Allometric respiration coefficient (mg O₂/g/h at 28°C).
            Rosas et al. (2001): a ≈ 0.30 for P. vannamei.
        resp_b: Allometric mass exponent (dimensionless, negative).
            Rosas et al. (2001): b ≈ −0.25.
        resp_theta: Arrhenius θ for respiration. Standard 1.08.
        resp_T_ref: Reference temperature for Arrhenius correction (°C). Default 28°C.
        resp_do_half_sat: DO half-saturation for respiration (mg/L).
            Below this DO, metabolic rate is suppressed.
        tan_per_feed: TAN excreted per g feed (g TAN/g feed).
            Hargreaves (1998): ~2.5% of feed as TAN.
        stress_do_threshold: DO below which stress mortality begins (mg/L).
        stress_nh3_threshold: Un-ionized NH₃ above which stress mortality begins (mg/L).
        stress_mortality_rate: Max additional mortality rate (fraction/day) at full stress.
        t_opt: Optimal temperature for growth (°C). Vannamei: 23-30°C.
        t_max: Maximum survivable temperature (°C). Default 35°C.
        feed_table_weight: Body weights for feed rate lookup table (g).
        feed_table_pct_bw: Feed rates corresponding to weights (% BW/day).
    """

    stocking_density_m2: float = 100.0
    fcr: float = 1.5
    resp_a: float = 0.30
    resp_b: float = -0.25
    resp_theta: float = 1.08
    resp_T_ref: float = 28.0
    resp_do_half_sat: float = 2.0
    tan_per_feed: float = 0.025
    stress_do_threshold: float = 2.0
    stress_nh3_threshold: float = 0.10
    stress_mortality_rate: float = 0.05  # fraction/day
    t_opt: float = 28.0
    t_max: float = 35.0
    feed_table_weight: list[float] = field(
        default_factory=lambda: [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
    )
    feed_table_pct_bw: list[float] = field(
        default_factory=lambda: [8.0, 7.0, 6.0, 5.0, 4.5, 4.0, 3.0, 2.5]
    )

    @classmethod
    def from_config(cls, cfg: object) -> "ShrimpParams":
        """Construct from ShrimpConfig."""
        return cls(
            stocking_density_m2=cfg.stocking_density_m2,
            fcr=cfg.fcr,
            resp_a=cfg.resp_coef_a,
            resp_b=cfg.resp_coef_b,
            resp_theta=cfg.resp_theta,
            resp_do_half_sat=cfg.resp_do_half_sat,
            tan_per_feed=cfg.tan_per_feed,
            stress_do_threshold=cfg.stress_do_threshold,
            stress_nh3_threshold=cfg.stress_nh3_threshold,
            stress_mortality_rate=cfg.stress_mortality_rate,
            t_opt=cfg.t_opt,
            t_max=cfg.t_max,
            feed_table_weight=list(cfg.feed_table_weight),
            feed_table_pct_bw=list(cfg.feed_table_pct_bw),
        )


def _interpolate_feed_rate(W_g: float, weights: list[float], rates: list[float]) -> float:
    """Linearly interpolate feed rate from table.

    Args:
        W_g: Current body weight (g).
        weights: Weight lookup table (g).
        rates: Feed rate lookup table (% BW/day).

    Returns:
        Feed rate (% BW/day).
    """
    if W_g <= weights[0]:
        return rates[0]
    if W_g >= weights[-1]:
        return rates[-1]
    for i in range(len(weights) - 1):
        if weights[i] <= W_g <= weights[i + 1]:
            frac = (W_g - weights[i]) / (weights[i + 1] - weights[i])
            return rates[i] + frac * (rates[i + 1] - rates[i])
    return rates[-1]


def _shrimp_respiration_o2(
    W_g: float,
    T_C: float,
    DO: float,
    params: ShrimpParams,
) -> float:
    """Individual shrimp O₂ consumption rate (mg O₂/g shrimp/h).

    VO₂ = a · W^b · θ^(T − T_ref) · f(DO)

    where f(DO) = DO / (K_DO + DO) suppresses metabolic rate at low O₂.

    Args:
        W_g: Body weight (g).
        T_C: Temperature (°C).
        DO: Dissolved oxygen (mg/L).
        params: ShrimpParams.

    Returns:
        O₂ consumption (mg O₂/g shrimp/h).

    References:
        Rosas et al. (2001). Aquaculture, 195, 277-289.
    """
    if W_g <= 0.0:
        return 0.0
    base_rate = params.resp_a * (W_g ** params.resp_b)
    temp_factor = params.resp_theta ** (T_C - params.resp_T_ref)
    do_factor = DO / (params.resp_do_half_sat + DO + 1e-12)
    return base_rate * temp_factor * do_factor


def _stress_mortality(
    DO: float,
    nh3_mg_L: float,
    params: ShrimpParams,
) -> float:
    """Stress-induced mortality rate (fraction/hour).

    Uses logistic stress functions:
        stress_DO = max(0, 1 - DO/DO_threshold)
        stress_NH3 = max(0, min(1, NH3/NH3_threshold))
    Combined mortality = stress_mortality_rate * max(stress_DO, stress_NH3) / 24

    Args:
        DO: Dissolved oxygen (mg/L).
        nh3_mg_L: Un-ionized ammonia concentration (mg NH₃-N/L).
        params: ShrimpParams.

    Returns:
        Additional mortality rate (fraction/hour).
    """
    do_stress = max(0.0, 1.0 - DO / max(params.stress_do_threshold, 0.1))
    do_stress = do_stress**2  # quadratic response

    nh3_stress = min(1.0, nh3_mg_L / max(params.stress_nh3_threshold, 1e-6))
    nh3_stress = nh3_stress**2

    combined_stress = max(do_stress, nh3_stress)
    return params.stress_mortality_rate * combined_stress / 24.0  # h⁻¹


def update_shrimp(
    state: ShrimpState,
    T_C: float,
    DO: float,
    nh3_mg_L: float,
    dt_h: float,
    params: ShrimpParams,
    feed_multiplier: float = 1.0,
    pond_area_m2: float = 5000.0,
) -> tuple[ShrimpState, float, float, float]:
    """Update shrimp state over a time step dt_h.

    Computes respiration, growth, excretion, and mortality, returns rates
    needed by the coupled ODE system (O₂ demand, TAN production).

    Args:
        state: Current ShrimpState.
        T_C: Water temperature (°C).
        DO: Dissolved oxygen (mg/L).
        nh3_mg_L: Un-ionized ammonia (mg NH₃-N/L).
        dt_h: Time step (hours).
        params: ShrimpParams.
        feed_multiplier: Multiplier on standard feed rate (0.5-1.5).
        pond_area_m2: Pond surface area (m²) for biomass normalization.

    Returns:
        Tuple of (new_state, R_shrimp_o2, E_shrimp_tan, mortality_rate) where:
            R_shrimp_o2: Shrimp O₂ demand (mg O₂/L/h), volume-averaged.
            E_shrimp_tan: TAN excretion (mg N/L/h), volume-averaged.
            mortality_rate: Mortality rate (fraction/h).

    References:
        Rosas et al. (2001), Hargreaves (1998), Boyd & Tucker (1998).
    """
    W = max(state.W_g, 0.01)
    B = max(state.B_g_m2, 0.0)
    surv = max(state.survival, 0.0)

    # Current density (shrimp/m²)
    density = B / W if W > 0 else 0.0

    # Feed rate (% BW/day → g feed/shrimp/day)
    feed_pct_bw = _interpolate_feed_rate(W, params.feed_table_weight, params.feed_table_pct_bw)
    feed_g_shrimp_d = W * feed_pct_bw / 100.0 * feed_multiplier

    # Growth rate (g/shrimp/h) from feed conversion
    # Temperature factor on growth (Eppley-like)
    t_factor = max(0.0, 1.0 - ((T_C - params.t_opt) / (params.t_max - params.t_opt)) ** 2)
    growth_g_shrimp_h = (feed_g_shrimp_d / params.fcr) * t_factor / 24.0

    # Individual respiration (mg O₂/g shrimp/h)
    resp_ind = _shrimp_respiration_o2(W, T_C, DO, params)

    # Population O₂ demand: mg O₂/m²/h = resp_ind * B
    # Convert to mg O₂/L/h using pond depth
    # We return per-unit-depth; caller uses pond depth
    R_shrimp_o2_m2 = resp_ind * B  # mg O₂/m²/h

    # TAN excretion: g TAN/shrimp/day → mg N/L/h
    # E = tan_per_feed * feed_g_shrimp_d / shrimp/m² / depth / 1000 mg/g / 24 h
    E_shrimp_tan_m2 = params.tan_per_feed * feed_g_shrimp_d * density * 1000.0 / 24.0  # mg N/m²/h

    # Stress mortality
    mort_rate_h = _stress_mortality(DO, nh3_mg_L, params)

    # Update state (Euler over dt_h)
    W_new = W + growth_g_shrimp_h * dt_h
    surv_new = surv * math.exp(-mort_rate_h * dt_h)
    # Biomass: density × W × survival fraction
    # n0 = initial_density (fixed); current n = n0 × surv_new
    n0 = params.stocking_density_m2
    B_new = n0 * surv_new * W_new

    new_state = ShrimpState(W_g=W_new, B_g_m2=B_new, survival=surv_new)
    return new_state, R_shrimp_o2_m2, E_shrimp_tan_m2, mort_rate_h
