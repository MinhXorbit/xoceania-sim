"""pH and inorganic carbon (C_T) ODE subsystem.

dC_T/dt = R_resp + R_shrimp + SOD_C/H − P_photo − (k_L·a_CO2/H)·(CO2 − CO2_atm)

pH is not an ODE state but is solved algebraically from C_T and total alkalinity
via Newton-Raphson iteration on the carbonate equilibrium system.

Dissociation constants K1, K2, Kw, KH are temperature and salinity corrected
following Millero (2010) / Dickson et al. (2007).

References:
    Millero, F.J. (2010). Carbonate constants for estuarine waters.
        Marine and Freshwater Research, 61, 139-142.
    Stumm, W. & Morgan, J.J. (1996). Aquatic Chemistry, 3rd ed. Wiley.
    Hargreaves, J.A. (1998). Nitrogen biogeochemistry of aquaculture ponds.
        Aquaculture, 166, 181-212.
    Chapra, S.C. et al. (2006). QUAL2Kw. Ecological Modelling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from xoceania_sim.forcing.forcing import ForcingState


@dataclass
class CarbonParams:
    """Parameters for pH and carbonate chemistry.

    Args:
        depth_m: Pond depth H (m).
        salinity_ppt: Salinity (ppt) for equilibrium constant correction.
        kLa_CO2_20: CO₂ gas transfer coefficient at 20°C (h⁻¹).
            CO₂ transfers ~0.9× faster than O₂ (ratio of diffusivities^0.5).
        reaeration_theta: Temperature coefficient for gas transfer.
        alkalinity_mg_L: Total alkalinity as CaCO₃ (mg/L). Slowly varying.
        co2_atm_ppm: Atmospheric CO₂ (ppm). Default 420 ppm (current).
        resp_CT_ratio: C_T produced per unit O₂ consumed (mol C / mol O₂).
            Respiratory quotient RQ ≈ 1.0 for mixed substrates.
        photo_CT_ratio: C_T consumed per unit O₂ produced (mol C / mol O₂).
            Photosynthetic quotient PQ ≈ 1.0 for algae.
    """

    depth_m: float = 1.5
    salinity_ppt: float = 15.0
    kLa_CO2_20: float = 2.0   # CO2 gas exchange h-1; includes aerator enhancement
    reaeration_theta: float = 1.024
    alkalinity_mg_L: float = 120.0
    co2_atm_ppm: float = 420.0
    resp_CT_ratio: float = 1.0  # mol C / mol O₂
    photo_CT_ratio: float = 1.0

    @classmethod
    def from_config(cls, cfg: object) -> "CarbonParams":
        return cls(
            depth_m=cfg.depth_m,
            salinity_ppt=cfg.salinity_ppt,
            alkalinity_mg_L=cfg.alkalinity_mg_L,
        )


def _carbonate_constants(T_C: float, S: float) -> Tuple[float, float, float, float]:
    """Temperature and salinity corrected carbonate equilibrium constants.

    Returns K1, K2 (mol/L), Kw (mol²/L²), KH (mol/L/atm).

    Uses Millero (2010) formulations for estuarine/brackish water.

    Args:
        T_C: Temperature (°C).
        S: Salinity (ppt).

    Returns:
        Tuple of (K1, K2, Kw, KH).

    References:
        Millero, F.J. (2010). Marine and Freshwater Research, 61, 139-142.
        Dickson, A.G. et al. (2007). Guide to best practices for CO₂ measurement.
    """
    T_K = T_C + 273.15
    sqrtS = math.sqrt(S)

    # K1 (mol/kg): Millero (2010) Table 5
    ln_K1 = (
        2.83655
        - 2307.1266 / T_K
        - 1.5529413 * math.log(T_K)
        + (-0.20760841 - 4.0484 / T_K) * sqrtS
        + 0.08468345 * S
        - 0.00654208 * S**1.5
        + math.log(1.0 - 0.001005 * S)
    )
    K1 = math.exp(ln_K1)

    # K2 (mol/kg): Millero (2010) Table 6
    ln_K2 = (
        -9.226508
        - 3351.6106 / T_K
        - 0.2005743 * math.log(T_K)
        + (-0.106901773 - 23.9722 / T_K) * sqrtS
        + 0.1130822 * S
        - 0.00846934 * S**1.5
        + math.log(1.0 - 0.001005 * S)
    )
    K2 = math.exp(ln_K2)

    # Kw (mol²/kg²): Millero (1995) freshwater adapted
    ln_Kw = (
        148.9652
        - 13847.26 / T_K
        - 23.6521 * math.log(T_K)
        + (118.67 / T_K - 5.977 + 1.0495 * math.log(T_K)) * sqrtS
        - 0.01615 * S
    )
    Kw = math.exp(ln_Kw)

    # KH (Henry's law, mol/L/atm): Weiss (1974)
    ln_KH = (
        -60.2409
        + 93.4517 / (T_K / 100.0)
        + 23.3585 * math.log(T_K / 100.0)
        + S * (0.023517 - 0.023656 * (T_K / 100.0) + 0.0047036 * (T_K / 100.0) ** 2)
    )
    KH = math.exp(ln_KH)  # mol/L/atm

    return K1, K2, Kw, KH


def solve_pH(
    CT_mmol_L: float,
    alkalinity_mg_L: float,
    T_C: float,
    salinity_ppt: float = 0.0,
    max_iter: int = 50,
    tol: float = 1e-9,
) -> Tuple[float, float]:
    """Solve for pH and free CO₂ given C_T and total alkalinity.

    Newton-Raphson iteration on the carbonate alkalinity equation:
        Alk = C_T·(K1·[H⁺] + 2K1K2) / ([H⁺]² + K1[H⁺] + K1K2)
              + Kw/[H⁺] − [H⁺]

    where Alk is in mol/L and C_T is in mol/L.

    Args:
        CT_mmol_L: Total dissolved inorganic carbon (mmol/L).
        alkalinity_mg_L: Total alkalinity as CaCO₃ (mg/L).
        T_C: Temperature (°C).
        salinity_ppt: Salinity (ppt).
        max_iter: Maximum Newton-Raphson iterations.
        tol: Convergence tolerance on [H⁺] (mol/L).

    Returns:
        Tuple of (pH, CO2_aq_mg_L) where CO2_aq is free CO₂ in mg/L.

    References:
        Stumm & Morgan (1996). Aquatic Chemistry, 3rd ed.
        Millero (2010). Marine and Freshwater Research, 61, 139-142.
    """
    # Convert units
    CT = max(CT_mmol_L * 1e-3, 1e-10)  # mol/L
    # Alkalinity: mg/L as CaCO3 → mol/L (equiv/L)
    # 1 meq/L = 1 mmol/L alkalinity (as CaCO3/2 = 50 mg per meq)
    Alk = max(alkalinity_mg_L / 50000.0, 1e-10)  # mol/L

    K1, K2, Kw, KH = _carbonate_constants(T_C, salinity_ppt)

    # Initial guess: Henderson-Hasselbalch for carbonate buffer
    # At typical aquaculture pH 7-9, dominated by HCO3-/CO2 pair
    if CT > 0 and Alk > 0:
        if Alk >= 2.0 * CT:
            pH_guess = 9.5  # mostly CO3^2- dominated
        elif Alk >= CT:
            # pH above pK1, near bicarbonate point
            pH_guess = -math.log10(K1) + math.log10(min(Alk / max(CT - Alk, 1e-10), 100.0))
            pH_guess = max(6.0, min(10.5, pH_guess))
        else:
            # pH near pK1 or below
            pH_guess = -math.log10(K1) + math.log10(Alk / max(CT - Alk, 1e-10) + 1e-10)
            pH_guess = max(5.0, min(9.0, pH_guess))
    else:
        pH_guess = 7.5
    H = 10.0 ** (-pH_guess)

    for _ in range(max_iter):
        H = max(H, 1e-14)
        D = H**2 + K1 * H + K1 * K2

        # Carbonate alkalinity contributions
        alk_carb = CT * (K1 * H + 2.0 * K1 * K2) / D
        alk_calc = alk_carb + Kw / H - H

        # Residual
        f = alk_calc - Alk

        # Derivative df/dH
        dD_dH = 2.0 * H + K1
        d_alk_carb_dH = CT * (K1 * D - (K1 * H + 2.0 * K1 * K2) * dD_dH) / D**2
        df_dH = d_alk_carb_dH - Kw / H**2 - 1.0

        H_new = H - f / df_dH
        H_new = max(1e-14, min(1.0, H_new))
        if abs(H_new - H) < tol:
            H = H_new
            break
        H = H_new

    pH = -math.log10(max(H, 1e-14))
    # Cap pH at 9.8: bicarbonate endpoint realistic for intensive ponds
    # Above pH 9.5, algal growth inhibited by OH- toxicity
    pH = max(4.0, min(9.8, pH))

    # Free CO2: [CO2(aq)] = C_T · [H⁺]² / D
    D = H**2 + K1 * H + K1 * K2
    CO2_aq_mol_L = CT * H**2 / D
    CO2_aq_mg_L = CO2_aq_mol_L * 44011.0  # mg/L (MW of CO2 = 44.011 g/mol)

    return pH, CO2_aq_mg_L


def dCT_dt(
    CT_mmol_L: float,
    T_C: float,
    forcing: ForcingState,
    params: CarbonParams,
    R_algae_O2: float,
    R_shrimp_O2: float,
    P_gross_O2: float,
    R_nitr_N: float,
) -> float:
    """Rate of change of total dissolved inorganic carbon (mmol/L/h).

    dC_T/dt = (R_resp_total / PQ) − (P_photo / PQ)
              − k_L·a_CO2·(CO2_aq − CO2_eq) / H

    All respiratory processes add C_T; photosynthesis removes it.
    CO₂ air-sea exchange depends on free CO₂ vs. atmospheric equilibrium.

    Args:
        CT_mmol_L: Current C_T (mmol/L).
        T_C: Water temperature (°C).
        forcing: ForcingState.
        params: CarbonParams.
        R_algae_O2: Algal respiration (mg O₂/L/h).
        R_shrimp_O2: Shrimp respiration (mg O₂/L/h).
        P_gross_O2: Gross photosynthetic O₂ production (mg O₂/L/h).
        R_nitr_N: Nitrification rate (mg N/L/h); adds CO₂ via acid production.

    Returns:
        dC_T/dt in mmol/L/h.

    References:
        Culberson & Piedrahita (1996). Ecol. Modelling, 89, 231-258.
        Hargreaves (1998). Aquaculture, 166, 181-212.
    """
    K1, K2, Kw, KH = _carbonate_constants(T_C, params.salinity_ppt)

    # Conversion: mg O₂/L/h → mmol C/L/h using RQ=1, PQ=1
    # 1 mg O₂/L/h × (1 mmol/32 mg) = 1/32 mmol O₂/L/h = 1/32 mmol C/L/h
    O2_to_C_mmol = 1.0 / 32.0  # mmol C per mg O₂

    # Respiration sources (add C_T)
    R_resp_mmol = (R_algae_O2 + R_shrimp_O2) * O2_to_C_mmol  # mmol/L/h

    # Nitrification: 2H+ per mol N → consumes 2 mmol alkalinity per mmol N
    # In terms of C_T effect: H+ addition shifts DIC equilibrium, effectively releasing CO2
    # Approximation: treat as C_T source equal to 0.5 × nitrification rate (simplified)
    R_nitr_C = R_nitr_N / 14.0 * 0.5  # mmol C/L/h (partial acidification)

    # SOD CO2 source: use fixed fraction (anaerobic sediment processes add CO2)
    # Approximate: SOD_CO2 ≈ 0.5 × SOD_O2 / depth for anaerobic portion
    # Already included implicitly via community respiration

    # Photosynthesis sink (remove C_T)
    P_photo_mmol = P_gross_O2 * O2_to_C_mmol  # mmol/L/h

    # Air-sea CO₂ exchange
    # CO₂ equilibrium with atmosphere: CO2_eq = KH × pCO2_atm
    pCO2_atm = params.co2_atm_ppm * 1e-6  # atm
    CO2_eq_mol_L = KH * pCO2_atm  # mol/L
    CO2_eq_mmol_L = CO2_eq_mol_L * 1000.0  # mmol/L

    # Current free CO2 from C_T and alkalinity
    _, CO2_free_mg_L = solve_pH(CT_mmol_L, params.alkalinity_mg_L, T_C, params.salinity_ppt)
    CO2_free_mmol_L = CO2_free_mg_L / 44.011  # mmol/L

    # k_L·a for CO₂ (h⁻¹): CO₂ diffuses ~0.9× O₂ rate
    kLa_CO2 = params.kLa_CO2_20 * params.reaeration_theta ** (T_C - 20.0)
    # Gas exchange: positive = outgassing (CO2_free > CO2_eq)
    R_gas_exch = kLa_CO2 * (CO2_free_mmol_L - CO2_eq_mmol_L)

    dCT = R_resp_mmol + R_nitr_C - P_photo_mmol - R_gas_exch

    return dCT
