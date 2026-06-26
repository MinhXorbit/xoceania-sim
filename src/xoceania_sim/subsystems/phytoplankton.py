"""Phytoplankton biomass ODE subsystem.

dA/dt = (μ_g − μ_d − v_s/H) · A

Growth rate: μ_g = μ_max · f(T) · f(I) · f(N)
  f(T): Eppley (1972) exponential temperature dependence
  f(I): Steele (1962) photoinhibition model
  f(N): Monod on TAN (simplified — no separate NO3/PO4 tracking)

References:
    Steele, J.H. (1962). Environmental control of photosynthesis in the sea.
        Limnology and Oceanography, 7, 137-150.
    Eppley, R.W. (1972). Temperature and phytoplankton growth in the sea.
        Fisheries Bulletin, 70, 1063-1085.
    Monod, J. (1949). The growth of bacterial cultures.
        Annual Review of Microbiology, 3, 371-394.
    Culberson & Piedrahita (1996). Ecol. Modelling, 89, 231-258.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from xoceania_sim.forcing.forcing import ForcingState


@dataclass
class PhytoplanktonParams:
    """Parameters for phytoplankton dynamics.

    Args:
        depth_m: Mean water depth H (m).
        k_d: Light extinction coefficient (m⁻¹).
        mu_max_20: Maximum specific growth rate at 20°C (h⁻¹).
            Typical freshwater algae: 1.0-3.0 d⁻¹ ≈ 0.042-0.125 h⁻¹ at 25°C.
            Eppley (1972): μ_max ≈ 0.042 h⁻¹ at 20°C.
        I_opt: Optimal light intensity for Steele model (W/m²).
            Steele (1962): I_opt typically 100-300 W/m² for tropical algae.
        K_N: Nitrogen (TAN) half-saturation constant (mg N/L).
            Monod (1949): 0.01-0.2 mg N/L for phytoplankton.
        resp_rate_20: Dark respiration rate at 20°C (h⁻¹).
            Typical: 0.05-0.15 d⁻¹ ≈ 0.002-0.006 h⁻¹.
        mortality_rate: Non-respiratory mortality + grazing loss (h⁻¹).
        settling_rate_m_d: Settling velocity v_s (m/day).
            Typical for phytoplankton: 0.1-0.5 m/day.
        theta_growth: Arrhenius θ for growth. Eppley (1972): 1.066.
        theta_resp: Arrhenius θ for respiration. Default: 1.05.
        o2_per_chl: O₂ produced per mg Chl-a per h per unit f(I)f(N)f(T).
            Calibration factor linking Chl-a to O₂ production.
            Set so peak daytime P ≈ 5 mg/L/h at A = 200 mg Chl/m³.
            P = mu_g * A * o2_per_chl → need o2_per_chl in mg O2/(mg Chl · h⁻¹).
            Using P:C ratio ~1 mg O2 / μg Chl / d → /24 h.
        n_per_chl: Nitrogen content (mg N / mg Chl-a). Used for algal N uptake.
            Typical Redfield ratio: C:N:Chl ≈ 50:7:1, so N/Chl ≈ 0.1-0.5.
    """

    depth_m: float = 1.5
    k_d: float = 1.8
    mu_max_20: float = 0.065   # h⁻¹ at 20°C (≈ 1.56 d⁻¹)
    I_opt: float = 200.0       # W/m² optimal PAR
    K_N: float = 0.05          # mg N/L TAN half-saturation
    resp_rate_20: float = 0.05   # h⁻¹ (includes algal + community respiration; Boyd 1979)
    mortality_rate: float = 0.002  # h⁻¹
    settling_rate_m_d: float = 0.2  # m/day
    theta_growth: float = 1.066  # Eppley (1972)
    theta_resp: float = 1.05
    o2_per_chl: float = 60.0   # mg O₂ / (mg Chl/m³) / h at 100%% conditions
            # P = o2_per_chl * fI*fN*fT * A / 1000 mg O2/L/h
            # At A=100 mg/m3, fI*fN*fT=0.8: P = 60*0.8*100/1000 = 4.8 mg/L/h OK
    n_per_chl: float = 0.15    # mg N / mg Chl-a

    @classmethod
    def from_config(cls, cfg: object) -> "PhytoplanktonParams":
        return cls(depth_m=cfg.depth_m, k_d=cfg.extinction_coef_m)


def _growth_temp_factor(T_C: float, theta: float = 1.066) -> float:
    """Eppley (1972) temperature factor for phytoplankton growth.

    f(T) = θ^(T − 20)

    Args:
        T_C: Temperature (°C).
        theta: Arrhenius coefficient. Eppley (1972): θ = 1.066 (Q10 ≈ 1.88).

    Returns:
        Temperature limitation factor (dimensionless, > 0).

    References:
        Eppley, R.W. (1972). Fisheries Bulletin, 70, 1063-1085.
    """
    return theta ** (T_C - 20.0)


def _growth_light_factor(I_par_avg: float, I_opt: float) -> float:
    """Steele (1962) light limitation with photoinhibition.

    f(I) = (I / I_opt) · exp(1 − I / I_opt)

    Maximum f(I) = 1.0 at I = I_opt. For I >> I_opt, f → 0 (photoinhibition).

    Args:
        I_par_avg: Depth-averaged PAR (W/m²).
        I_opt: Optimal PAR (W/m²).

    Returns:
        Light limitation factor (0-1).

    References:
        Steele, J.H. (1962). Limnology and Oceanography, 7, 137-150.
    """
    if I_par_avg <= 0.0 or I_opt <= 0.0:
        return 0.0
    x = I_par_avg / I_opt
    return x * math.exp(1.0 - x)


def _growth_nutrient_factor(TAN: float, K_N: float) -> float:
    """Monod nutrient limitation on phytoplankton growth.

    f(N) = TAN / (K_N + TAN)

    Args:
        TAN: Total ammonia nitrogen (mg N/L). Used as primary N source.
        K_N: Half-saturation constant (mg N/L).

    Returns:
        Nutrient limitation factor (0-1).

    References:
        Monod, J. (1949). Ann. Rev. Microbiology, 3, 371-394.
    """
    if TAN <= 0.0:
        return 0.0
    return TAN / (K_N + TAN)



def _growth_ct_factor(CT_mmol_L: float, K_CO2: float = 0.1) -> float:
    """CO2/carbon limitation on phytoplankton growth.
    
    At very low CT, photosynthesis becomes carbon-limited.
    Uses Monod kinetics on CT: f(CT) = CT / (K_CO2 + CT)
    This naturally limits pH by preventing unlimited CO2 drawdown.
    
    Args:
        CT_mmol_L: Total dissolved inorganic carbon (mmol/L).
        K_CO2: Half-saturation constant (mmol/L). Default 0.1.
    
    Returns:
        Carbon limitation factor (0-1).
    """
    return CT_mmol_L / (K_CO2 + CT_mmol_L + 1e-12)

def dA_dt(
    A: float,
    T_C: float,
    TAN: float,
    forcing: ForcingState,
    params: PhytoplanktonParams,
    pH: float = 8.0,
    CT_mmol_L: float = 2.0,
) -> tuple[float, float, float]:
    """Rate of change of phytoplankton chlorophyll-a (mg Chl/m³/h).

    dA/dt = (μ_g − μ_d − v_s/H) · A

    where:
        μ_g = μ_max · f(T) · f(I) · f(N)  [growth]
        μ_d = resp_rate + mortality_rate    [loss]
        v_s/H = settling loss              [sedimentation]

    Args:
        A: Phytoplankton chlorophyll-a concentration (mg Chl/m³).
        T_C: Water temperature (°C).
        TAN: Total ammonia nitrogen (mg N/L).
        forcing: ForcingState with depth-averaged PAR.
        params: PhytoplanktonParams.

    Returns:
        Tuple of (dA/dt, P_gross_o2, R_algae_o2) all in mg/m³ or mg/L per h.
        P_gross_o2 and R_algae_o2 are in mg O₂/L/h (used by DO subsystem).

    References:
        Steele (1962), Eppley (1972), Monod (1949), Culberson & Piedrahita (1996).
    """
    A_eff = max(A, 0.0)

    # Limitation factors
    fT = _growth_temp_factor(T_C, params.theta_growth)
    fI = _growth_light_factor(forcing.I_par_avg, params.I_opt)
    fN = _growth_nutrient_factor(TAN, params.K_N)

    # Gross growth rate (h⁻¹)
    # CT limitation: prevents unrealistic CO2 drawdown  
    fCT = _growth_ct_factor(CT_mmol_L, K_CO2=0.05)  # K_CO2=0.05 mmol/L
    mu_g = params.mu_max_20 * fT * fI * fN * fCT


    # Respiration rate (h⁻¹), temperature corrected
    mu_resp = params.resp_rate_20 * params.theta_resp ** (T_C - 20.0)

    # pH limitation: growth suppressed outside pH 6-10 range
    # Algae grow optimally at pH 7-9; strongly inhibited above pH 9.5
    pH_opt_lo, pH_opt_hi = 7.0, 9.0
    if pH < pH_opt_lo:
        fPH = max(0.0, (pH - 5.0) / (pH_opt_lo - 5.0))
    elif pH > pH_opt_hi:
        fPH = max(0.0, 1.0 - (pH - pH_opt_hi) / 2.0)
    else:
        fPH = 1.0

    mu_g = mu_g * fPH  # apply pH limitation

    # Settling loss (h⁻¹)
    v_s_h = params.settling_rate_m_d / 24.0 / params.depth_m  # h⁻¹

    # Net growth rate
    mu_net = mu_g - mu_resp - params.mortality_rate - v_s_h

    # Rate of change (mg Chl/m³/h)
    dA = mu_net * A_eff

    # O₂ production by photosynthesis: P_gross (mg O₂/L/h)
    # P = μ_g * A * o2_per_chl (A in mg Chl/m³ = μg Chl/L; convert /1000 to mg Chl/L)
    # O2 production: P = Pmax_chl * fI * fN * fT * A / 1000 (A in mg Chl/m3, /1000 to get mg Chl/L equiv)
    # At A=100 mg/m3, Pmax_chl=60, fI*fN*fT=0.8: P = 60*0.8*100/1000 = 4.8 mg O2/L/h (typical pond)
    P_gross_o2 = params.o2_per_chl * fI * fN * fT * A_eff / 1000.0  # mg O₂/L/h

    # Algal dark respiration O₂ demand
    # Respiration: ~10-15% of gross photosynthesis capacity
    R_algae_o2 = params.resp_rate_20 * params.theta_resp ** (T_C - 20.0) * A_eff * params.o2_per_chl / 1000.0  # mg O₂/L/h

    return dA, P_gross_o2, R_algae_o2
