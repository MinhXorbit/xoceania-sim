"""Water temperature ODE subsystem.

Computes dT/dt = Φ_net / (ρ · Cₚ · H) via full surface energy balance:
    Φ_net = Φ_sw_net + Φ_lw_in − Φ_lw_out − Φ_evap − Φ_conv

Uses Stefan-Boltzmann longwave radiation, Dalton-type evaporation,
and Bowen-ratio convection.

References:
    Losordo, T.M. & Piedrahita, R.H. (1991). Modelling temperature variation
        and thermal stratification in shallow aquaculture ponds. Ecol. Modelling,
        54, 189-226.
    Culberson, S.D. & Piedrahita, R.H. (1996). Aquaculture pond ecosystem model:
        temperature and dissolved oxygen prediction. Ecol. Modelling, 89, 231-258.
    Béchet, Q. et al. (2011). Universal temperature model for shallow algal ponds.
        Environmental Science & Technology, 45, 3702-3709.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from xoceania_sim.forcing.forcing import ForcingState


@dataclass
class TemperatureParams:
    """Parameters for the pond thermal energy balance.

    Args:
        depth_m: Mean water depth (m).
        surface_albedo: Water surface albedo (dimensionless). Typical: 0.06.
        emissivity_water: Emissivity of water surface. ε_water = 0.97.
        wind_f0: Dalton evaporation wind function coefficient f₀ (W/m²/mbar).
            Ryner et al. (1986): f₀ ≈ 2.7, f₁ ≈ 3.1 × u_wind.
        wind_f1: Dalton wind function linear coefficient f₁.
        bowen_ratio_const: Psychrometric constant γ for Bowen ratio (mbar/°C).
            Standard atmosphere: γ = 0.61 mbar/°C at 25°C.
    """

    depth_m: float = 1.5
    surface_albedo: float = 0.06
    emissivity_water: float = 0.97
    wind_f0: float = 2.7
    wind_f1: float = 3.1
    bowen_ratio_const: float = 0.61

    @classmethod
    def from_pond_config(cls, cfg: object) -> "TemperatureParams":
        """Construct from PondConfig."""
        return cls(
            depth_m=cfg.depth_m,
            surface_albedo=cfg.surface_albedo,
        )


# Physical constants
_SIGMA = 5.670374419e-8  # Stefan-Boltzmann constant (W/m²/K⁴)
_RHO_W = 997.0           # Water density (kg/m³)
_CP_W = 4182.0           # Specific heat of water at 25°C (J/kg/K)
_L_V = 2.45e6            # Latent heat of vaporization of water (J/kg)


def _sat_vapor_pressure_mbar(T_C: float) -> float:
    """Saturated vapor pressure at temperature T_C (°C) in mbar.

    Uses Buck (1981) equation accurate to 0.1% for 0-50°C.

    Args:
        T_C: Temperature in °C.

    Returns:
        Saturated vapor pressure in mbar (hPa).
    """
    return 6.1121 * math.exp((17.368 * T_C) / (238.88 + T_C))


def _longwave_in(T_air_K: float, emissivity_water: float) -> float:
    """Incoming atmospheric longwave radiation (W/m²).

    Uses Brunt (1932) formula for effective sky emissivity with water vapor.
    For simplicity, uses clear-sky formula: ε_sky ≈ 0.97 (close to unity at Mekong humidity).

    Args:
        T_air_K: Air temperature (K).
        emissivity_water: Water emissivity (used as sky emissivity proxy).

    Returns:
        Downwelling longwave irradiance (W/m²).
    """
    eps_sky = 0.97  # effective clear-sky emissivity at 80% RH (Brunt 1932)
    return eps_sky * _SIGMA * T_air_K**4


def _longwave_out(T_water_K: float, emissivity_water: float) -> float:
    """Outgoing longwave radiation from pond surface (W/m²) — Stefan-Boltzmann.

    Args:
        T_water_K: Water surface temperature (K).
        emissivity_water: ε_water = 0.97 for water.

    Returns:
        Outgoing longwave irradiance (W/m²).
    """
    return emissivity_water * _SIGMA * T_water_K**4


def _evaporative_heat_loss(
    T_water_C: float,
    T_air_C: float,
    RH: float,
    u_wind_ms: float,
    wind_f0: float,
    wind_f1: float,
) -> float:
    """Evaporative heat flux from pond surface (W/m²).

    Uses Dalton-type (mass-transfer) formula:
        Φ_evap = f(u) · (e_s(T_water) − e_a)
        f(u) = f₀ + f₁ · u_wind (W/m²/mbar)
        e_a = RH · e_s(T_air)

    Args:
        T_water_C: Water surface temperature (°C).
        T_air_C: Air temperature (°C).
        RH: Relative humidity (fraction 0-1).
        u_wind_ms: Wind speed at 3 m (m/s).
        wind_f0: Wind function constant coefficient (W/m²/mbar).
        wind_f1: Wind function linear coefficient.

    Returns:
        Evaporative heat loss (W/m², positive = loss from pond).
    """
    e_s_water = _sat_vapor_pressure_mbar(T_water_C)
    e_s_air = _sat_vapor_pressure_mbar(T_air_C)
    e_a = RH * e_s_air  # actual vapor pressure in air
    vpd = e_s_water - e_a  # vapor pressure deficit
    f_u = wind_f0 + wind_f1 * u_wind_ms  # W/m²/mbar
    # Convert evaporative mass flux to heat flux via latent heat
    # f_u in W/m²/mbar gives direct Φ_evap
    phi_evap = f_u * max(0.0, vpd)
    return phi_evap


def _convective_heat_loss(
    T_water_C: float,
    T_air_C: float,
    RH: float,
    u_wind_ms: float,
    wind_f0: float,
    wind_f1: float,
    bowen_ratio_const: float,
) -> float:
    """Convective (sensible) heat flux via Bowen ratio.

    Bowen ratio: B_r = γ · (T_water − T_air) / (e_s(T_water) − e_a)
    Φ_conv = B_r · Φ_evap

    Args:
        T_water_C: Water surface temperature (°C).
        T_air_C: Air temperature (°C).
        RH: Relative humidity (fraction 0-1).
        u_wind_ms: Wind speed at 3 m (m/s).
        wind_f0: Wind function constant (W/m²/mbar).
        wind_f1: Wind function linear coefficient.
        bowen_ratio_const: Psychrometric constant γ (mbar/°C).

    Returns:
        Convective heat flux (W/m²). Positive = heat loss from pond.
    """
    e_s_water = _sat_vapor_pressure_mbar(T_water_C)
    e_s_air = _sat_vapor_pressure_mbar(T_air_C)
    e_a = RH * e_s_air
    vpd = e_s_water - e_a
    if abs(vpd) < 0.01:
        # Near-saturation: use direct convection
        f_u = wind_f0 + wind_f1 * u_wind_ms
        return f_u * bowen_ratio_const * (T_water_C - T_air_C)
    bowen = bowen_ratio_const * (T_water_C - T_air_C) / vpd
    phi_evap = _evaporative_heat_loss(T_water_C, T_air_C, RH, u_wind_ms, wind_f0, wind_f1)
    return bowen * phi_evap


def dT_dt(
    T_water_C: float,
    forcing: ForcingState,
    params: TemperatureParams,
) -> float:
    """Rate of change of pond water temperature (°C/h).

    Full energy balance:
        dT/dt = Φ_net / (ρ · Cₚ · H)
        Φ_net = (1 − α) · I_sw + Φ_lw_in − Φ_lw_out − Φ_evap − Φ_conv

    Args:
        T_water_C: Current water temperature (°C).
        forcing: ForcingState at current time.
        params: TemperatureParams.

    Returns:
        dT/dt in °C/hour.

    References:
        Losordo & Piedrahita (1991). Ecol. Modelling, 54, 189-226.
        Culberson & Piedrahita (1996). Ecol. Modelling, 89, 231-258.
    """
    T_water_K = T_water_C + 273.15
    T_air_K = forcing.T_air + 273.15

    # Net shortwave: (1 − α) · I_sw
    phi_sw = (1.0 - params.surface_albedo) * forcing.I_sw

    # Longwave balance
    phi_lw_in = _longwave_in(T_air_K, params.emissivity_water)
    phi_lw_out = _longwave_out(T_water_K, params.emissivity_water)

    # Evaporative and convective losses
    phi_evap = _evaporative_heat_loss(
        T_water_C, forcing.T_air, forcing.RH, forcing.u_wind,
        params.wind_f0, params.wind_f1,
    )
    phi_conv = _convective_heat_loss(
        T_water_C, forcing.T_air, forcing.RH, forcing.u_wind,
        params.wind_f0, params.wind_f1, params.bowen_ratio_const,
    )

    # Net heat flux (W/m²)
    phi_net = phi_sw + phi_lw_in - phi_lw_out - phi_evap - phi_conv

    # Temperature rate: dT/dt (°C/s)
    dT_s = phi_net / (_RHO_W * _CP_W * params.depth_m)

    # Convert to °C/hour
    return dT_s * 3600.0
