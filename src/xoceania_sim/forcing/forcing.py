"""Unified environmental forcing interface for xoceania-sim.

EnvironmentalForcing assembles solar and weather data into a ForcingState namedtuple
consumed by each ODE subsystem. The .at(t) method is the single entry point for all
forcing in the coupled integrator.

References:
    Bird & Hulstrom (1981): Clear-sky solar model. SERI/TR-642-761.
    Morel & Smith (1974): PAR fraction of shortwave. Limnol. Oceanogr., 19, 591-600.
"""

from __future__ import annotations

from typing import NamedTuple

from xoceania_sim.config import PondConfig, WeatherConfig
from xoceania_sim.forcing.solar import clear_sky_irradiance, par_underwater
from xoceania_sim.forcing.weather import SyntheticWeather, CSVWeather


class ForcingState(NamedTuple):
    """Environmental state at a given simulation time.

    Attributes:
        I_sw: Global shortwave irradiance at pond surface (W/m²).
        I_par: Surface PAR (W/m²). I_par = 0.47 × I_sw (Morel & Smith 1974).
        I_par_avg: Depth-averaged PAR (W/m²) via Beer-Lambert integration.
        T_air: Air temperature (°C).
        RH: Relative humidity (fraction 0-1).
        u_wind: Wind speed at 3 m height (m/s).
        cloud_cover: Cloud cover fraction (0-1).
        hour_of_day: Local solar hour (0-24).
        day_of_year: Day of year (1-365).
    """

    I_sw: float
    I_par: float
    I_par_avg: float
    T_air: float
    RH: float
    u_wind: float
    cloud_cover: float
    hour_of_day: float
    day_of_year: int


class EnvironmentalForcing:
    """Coupled solar + weather forcing for the pond ODE system.

    Combines Bird-Hulstrom solar irradiance with a weather data source (synthetic
    sinusoidal or CSV-observed) to produce ForcingState objects at arbitrary times.

    Args:
        pond_cfg: Pond configuration (provides lat/lon, depth, extinction coef).
        weather_cfg: Weather configuration (provides weather parameters).
        t_start_hours: Simulation start time in hours from midnight (default 0 = midnight).
        utc_offset_hours: Local UTC offset (hours). Mekong Delta: UTC+7.

    Example:
        >>> forcing = EnvironmentalForcing(pond_cfg, weather_cfg)
        >>> state = forcing.at(12.0)  # noon of day 1
        >>> state.I_par
        ...
    """

    def __init__(
        self,
        pond_cfg: PondConfig,
        weather_cfg: WeatherConfig,
        t_start_hours: float = 0.0,
        utc_offset_hours: float = 7.0,
    ) -> None:
        self._pond = pond_cfg
        self._weather_cfg = weather_cfg
        self._t0 = t_start_hours
        self._utc_offset = utc_offset_hours
        self._doy_start = weather_cfg.day_of_year

        # Build weather provider
        if weather_cfg.csv_path is not None:
            self._weather = CSVWeather(weather_cfg.csv_path, repeat=True)
        else:
            self._weather = SyntheticWeather(
                t_mean_C=weather_cfg.t_mean_C,
                t_amplitude_C=weather_cfg.t_amplitude_C,
                t_min_hour=weather_cfg.t_min_hour,
                rh_mean=weather_cfg.rh_mean,
                wind_speed_ms=weather_cfg.wind_speed_ms,
                cloud_cover_mean=weather_cfg.cloud_cover,
            )

    def at(self, t_hours: float) -> ForcingState:
        """Return ForcingState at simulation time t_hours.

        Args:
            t_hours: Simulation time in hours from simulation start.

        Returns:
            ForcingState namedtuple with all forcing variables.
        """
        # Absolute wall-clock hour since midnight on start day
        abs_hour = self._t0 + t_hours

        # Day of year (wrap at 365)
        abs_doy = self._doy_start + int(abs_hour // 24)
        doy = ((abs_doy - 1) % 365) + 1

        # Hour of day (local solar time, 0-24)
        hour_of_day = abs_hour % 24.0

        # Convert to UTC for solar model
        hour_utc = (hour_of_day - self._utc_offset) % 24.0

        # Solar irradiance (Bird-Hulstrom + Kasten-Czeplak cloud correction)
        cloud = self._weather.cloud_cover(t_hours)
        sol = clear_sky_irradiance(
            lat_deg=self._pond.latitude_deg,
            lon_deg=self._pond.longitude_deg,
            doy=doy,
            hour_utc=hour_utc,
            cloud_cover=cloud,
        )

        # Depth-averaged PAR
        I_par_avg = par_underwater(
            sol.I_par, self._pond.depth_m, self._pond.extinction_coef_m
        )

        # Weather state
        T_air = self._weather.air_temp_C(t_hours)
        RH = self._weather.rel_humidity(t_hours)
        u_wind = self._weather.wind_speed_ms(t_hours)

        return ForcingState(
            I_sw=sol.I_global,
            I_par=sol.I_par,
            I_par_avg=I_par_avg,
            T_air=T_air,
            RH=RH,
            u_wind=u_wind,
            cloud_cover=cloud,
            hour_of_day=hour_of_day,
            day_of_year=doy,
        )


def create_forcing(
    pond_cfg: PondConfig,
    weather_cfg: WeatherConfig,
    t_start_hours: float = 0.0,
    utc_offset_hours: float = 7.0,
) -> EnvironmentalForcing:
    """Factory function to create an EnvironmentalForcing instance.

    Args:
        pond_cfg: Pond physical configuration.
        weather_cfg: Weather generator configuration.
        t_start_hours: Start time in hours from midnight (e.g. 0 = midnight, 6 = dawn).
        utc_offset_hours: UTC offset for solar time conversion (Mekong Delta: 7).

    Returns:
        EnvironmentalForcing instance.
    """
    return EnvironmentalForcing(pond_cfg, weather_cfg, t_start_hours, utc_offset_hours)
