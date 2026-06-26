"""Configuration dataclasses for xoceania-sim.

All parameters are loadable from YAML. Default values represent Vietnamese intensive
Penaeus vannamei ponds in the Mekong Delta unless otherwise noted.

References:
    Boyd & Tucker (1998): Pond Aquaculture Water Quality Management.
    Hargreaves (1998): Nitrogen biogeochemistry of aquaculture ponds. Aquaculture.
    Culberson & Piedrahita (1996): Aquaculture Pond Ecosystem Model. Ecol. Modelling.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PondConfig:
    """Physical pond geometry and water chemistry parameters.

    Args:
        depth_m: Mean water depth (m). Boyd & Tucker (1998) typical intensive: 1.2-1.8 m.
        area_m2: Pond surface area (m²).
        salinity_ppt: Water salinity (parts per thousand, g/kg).
        alkalinity_mg_L: Total alkalinity as CaCO₃ (mg/L). Mekong Delta: 80-150 mg/L.
        latitude_deg: Pond latitude (degrees N).
        longitude_deg: Pond longitude (degrees E).
        extinction_coef_m: Light extinction coefficient k_d (m⁻¹).
            Eutrophic ponds: 1-5 m⁻¹. Weiskerger et al. (2018).
        surface_albedo: Pond surface albedo (dimensionless). Typical water: 0.06.
        n_aerators: Number of paddlewheel aerators.
        aerator_power_kW: Power per aerator (kW).
        aerator_kLa_20: Reaeration coefficient per aerator at 20°C (h⁻¹).
            Boyd (1979): paddlewheel ~ 0.5-1.5 h⁻¹ per 1 kW/m² pond area.
        sod_g_m2_d: Sediment oxygen demand (g O₂/m²/day).
            Boyd (1979) typical intensive: 1.5-3.0 g/m²/day.
        sod_theta: Temperature coefficient for SOD. Default 1.065. Bowie et al. (1985).
        wind_reaeration_coef: Boyd & Teichert-Coddington (1992) wind reaeration.
            KLa₂₀ = coef * U_wind - offset. coef = 0.017, offset = 0.014.
        wind_reaeration_offset: See wind_reaeration_coef.
        reaeration_theta: Temperature coefficient for wind reaeration. Default 1.024.
    """

    depth_m: float = 1.5
    area_m2: float = 5000.0
    salinity_ppt: float = 15.0
    alkalinity_mg_L: float = 120.0
    latitude_deg: float = 9.5
    longitude_deg: float = 105.0
    extinction_coef_m: float = 1.8
    surface_albedo: float = 0.06
    n_aerators: int = 2
    aerator_power_kW: float = 2.0
    aerator_kLa_20: float = 0.8
    sod_g_m2_d: float = 2.0
    sod_theta: float = 1.065
    wind_reaeration_coef: float = 0.017
    wind_reaeration_offset: float = 0.014
    reaeration_theta: float = 1.024


@dataclass
class ShrimpConfig:
    """Penaeus vannamei biological parameters.

    Args:
        initial_weight_g: Initial mean body weight per shrimp (g).
        target_weight_g: Target harvest weight (g).
        stocking_density_m2: Post-larvae stocking density (PL/m²).
        initial_survival: Initial survival fraction (0-1).
        fcr: Feed conversion ratio (g feed / g wet weight gain).
            Typical vannamei intensive: 1.3-1.7.
        resp_coef_a: Allometric respiration coefficient (mg O₂/g/h at 28°C).
            Rosas et al. (2001): a ≈ 0.30 for P. vannamei.
        resp_coef_b: Allometric mass exponent (dimensionless, negative).
            Rosas et al. (2001): b ≈ -0.25.
        resp_theta: Arrhenius temperature coefficient for respiration. Default 1.08.
        resp_do_half_sat: DO half-saturation for shrimp respiration (mg/L). ~2.0.
        tan_per_feed: TAN excreted per unit feed consumed (g TAN/g feed).
            Hargreaves (1998): ~2.5% nitrogen content of feed × ~1.0 excretion fraction.
        stress_do_threshold: DO below which mortality stress begins (mg/L). Default 2.0.
        stress_nh3_threshold: Un-ionized NH₃ above which mortality stress begins (mg/L).
            Boyd & Tucker (1998): LC50 for vannamei ~2.0 mg/L; chronic ~0.1 mg/L.
        stress_mortality_rate: Additional mortality rate at full stress (fraction/day).
        t_opt: Optimal temperature for growth (°C). Vannamei: 23-30°C.
        t_max: Maximum survivable temperature (°C). Default 35°C.
        feed_table_weight: Body weights for feed rate lookup (g).
        feed_table_pct_bw: Feed rates corresponding to weights (% BW/day).
    """

    initial_weight_g: float = 1.0
    target_weight_g: float = 20.0
    stocking_density_m2: float = 100.0
    initial_survival: float = 1.0
    fcr: float = 1.5
    resp_coef_a: float = 0.30
    resp_coef_b: float = -0.25
    resp_theta: float = 1.08
    resp_do_half_sat: float = 2.0
    tan_per_feed: float = 0.025
    stress_do_threshold: float = 2.0
    stress_nh3_threshold: float = 0.10
    stress_mortality_rate: float = 0.05
    t_opt: float = 28.0
    t_max: float = 35.0
    feed_table_weight: list[float] = field(
        default_factory=lambda: [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
    )
    feed_table_pct_bw: list[float] = field(
        default_factory=lambda: [8.0, 7.0, 6.0, 5.0, 4.5, 4.0, 3.0, 2.5]
    )


@dataclass
class WeatherConfig:
    """Synthetic weather generator parameters (Mekong Delta defaults).

    Args:
        t_mean_C: Mean daily air temperature (°C). Mekong Delta: ~28°C.
        t_amplitude_C: Daily temperature amplitude ΔT (°C). ΔT/2 is half-amplitude.
        t_min_hour: Hour of minimum daily temperature. Default 6 (06:00).
        rh_mean: Mean relative humidity (fraction 0-1). Mekong Delta: 0.80.
        wind_speed_ms: Mean wind speed at 3 m height (m/s). Default 3.0.
        cloud_cover: Mean cloud cover fraction (0-1). 0 = clear sky.
        day_of_year: Day of year (1-365) for solar calculations.
        csv_path: Optional path to CSV weather data file (overrides synthetic).
    """

    t_mean_C: float = 28.0
    t_amplitude_C: float = 8.0
    t_min_hour: float = 6.0
    rh_mean: float = 0.80
    wind_speed_ms: float = 3.0
    cloud_cover: float = 0.2
    day_of_year: int = 200
    csv_path: str | None = None


@dataclass
class SimConfig:
    """Top-level simulation configuration.

    Args:
        pond: Physical pond parameters.
        shrimp: Biological shrimp parameters.
        weather: Environmental forcing parameters.
        dt_hours: Default output time step (hours).
        t_end_days: Default simulation duration (days).
        solver_method: ODE solver method. LSODA handles stiffness automatically.
        rtol: Relative tolerance for ODE solver.
        atol: Absolute tolerance for ODE solver.
        initial_do: Initial dissolved oxygen (mg/L). Default 7.0.
        initial_temp: Initial water temperature (°C).
        initial_CT: Initial total dissolved inorganic carbon (mmol/L). Default 2.5.
        initial_TAN: Initial total ammonia nitrogen (mg N/L).
        initial_algae: Initial phytoplankton chlorophyll-a (mg Chl/m³).
        aeration_schedule: Dict mapping hour→aeration_fraction for time-varying control.
            None = always on at full capacity.
        feed_schedule: Dict mapping day→feed_multiplier. None = standard table.
        exchange_events: List of (day, fraction) tuples for water exchange events.
    """

    pond: PondConfig = field(default_factory=PondConfig)
    shrimp: ShrimpConfig = field(default_factory=ShrimpConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    dt_hours: float = 1.0
    t_end_days: float = 7.0
    solver_method: str = "LSODA"
    rtol: float = 1e-4
    atol: float = 1e-6
    initial_do: float = 7.0
    initial_temp: float = 28.0
    initial_CT: float = 2.5
    initial_TAN: float = 0.1
    initial_algae: float = 50.0
    aeration_schedule: dict[float, float] | None = None
    feed_schedule: dict[int, float] | None = None
    exchange_events: list[tuple[float, float]] = field(default_factory=list)


def _from_dict(cls: type, data: dict[str, Any]) -> Any:
    """Recursively instantiate a dataclass from a dict, handling nested dataclasses."""
    if not dataclasses.is_dataclass(cls):
        return data
    fields = {f.name: f for f in dataclasses.fields(cls)}
    kwargs: dict[str, Any] = {}
    for key, val in data.items():
        if key not in fields:
            continue
        f = fields[key]
        ft = f.type
        # Resolve string annotations
        if isinstance(ft, str):
            import sys
            import xoceania_sim.config as _cfg_mod
            ft = getattr(_cfg_mod, ft, None)
        if dataclasses.is_dataclass(ft) and isinstance(val, dict):
            kwargs[key] = _from_dict(ft, val)
        else:
            kwargs[key] = val
    return cls(**kwargs)


def load_config(path: str | Path) -> SimConfig:
    """Load a SimConfig from a YAML file.

    Args:
        path: Path to YAML configuration file.

    Returns:
        Fully populated SimConfig dataclass.

    Example:
        >>> cfg = load_config("configs/vannamei_mekong.yaml")
        >>> cfg.pond.depth_m
        1.5
    """
    path = Path(path)
    if not path.is_absolute():
        # Try relative to package install dir first, then cwd
        pkg_root = Path(__file__).parent.parent.parent.parent
        candidate = pkg_root / path
        if candidate.exists():
            path = candidate
    with open(path) as f:
        data = yaml.safe_load(f)

    pond_data = data.get("pond", {})
    shrimp_data = data.get("shrimp", {})
    weather_data = data.get("weather", {})
    sim_data = {k: v for k, v in data.items() if k not in ("pond", "shrimp", "weather")}

    return SimConfig(
        pond=_from_dict(PondConfig, pond_data),
        shrimp=_from_dict(ShrimpConfig, shrimp_data),
        weather=_from_dict(WeatherConfig, weather_data),
        **sim_data,
    )
