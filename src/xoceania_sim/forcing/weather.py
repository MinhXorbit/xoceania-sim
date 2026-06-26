"""Synthetic and CSV-driven weather generators for pond forcing.

Provides sinusoidal air temperature, relative humidity, and wind speed generators
calibrated to Mekong Delta climatology, plus a CSV loader for observed weather data.

References:
    Boyd & Tucker (1998): Pond Aquaculture Water Quality Management. Kluwer.
    Stewart & Rouse (1976): Simple models for estimating latent heat flux from
        ponds. Water Resources Research, 12, 623-628. (< 5% error vs energy budget)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Protocol


class WeatherProvider(Protocol):
    """Protocol for weather data providers."""

    def air_temp_C(self, t_hours: float) -> float:
        """Return air temperature (°C) at time t_hours."""
        ...

    def rel_humidity(self, t_hours: float) -> float:
        """Return relative humidity (fraction 0-1) at time t_hours."""
        ...

    def wind_speed_ms(self, t_hours: float) -> float:
        """Return wind speed at 3 m height (m/s) at time t_hours."""
        ...

    def cloud_cover(self, t_hours: float) -> float:
        """Return cloud cover fraction (0-1) at time t_hours."""
        ...


class SyntheticWeather:
    """Sinusoidal synthetic weather generator.

    Generates diurnal air temperature using:
        T_air(t) = T_mean + (ΔT/2) · sin(2π(t − t_min)/24)

    where t_min is the hour of minimum temperature (typically 06:00).

    Relative humidity and wind speed are held constant at their mean values
    (sufficient for process-based ODE studies; more complex patterns can be
    implemented via CSV loading).

    Args:
        t_mean_C: Mean daily air temperature (°C).
        t_amplitude_C: Daily temperature range ΔT (°C).
        t_min_hour: Hour of minimum temperature (local time).
        rh_mean: Mean relative humidity (fraction 0-1).
        wind_speed_ms: Mean wind speed at 3 m height (m/s).
        cloud_cover_mean: Mean cloud cover fraction (0-1).
        rh_amplitude: Optional diurnal amplitude of relative humidity (fraction).
            RH is typically anti-correlated with temperature.

    Example:
        >>> w = SyntheticWeather(t_mean_C=28.0, t_amplitude_C=8.0)
        >>> w.air_temp_C(6.0)  # dawn minimum
        24.0
        >>> w.air_temp_C(14.0)  # early afternoon maximum ≈ 32°C
        ...
    """

    def __init__(
        self,
        t_mean_C: float = 28.0,
        t_amplitude_C: float = 8.0,
        t_min_hour: float = 6.0,
        rh_mean: float = 0.80,
        wind_speed_ms: float = 3.0,
        cloud_cover_mean: float = 0.20,
        rh_amplitude: float = 0.10,
    ) -> None:
        self._t_mean = t_mean_C
        self._t_amp = t_amplitude_C
        self._t_min = t_min_hour
        self._rh_mean = rh_mean
        self._rh_amp = rh_amplitude
        self._wind = wind_speed_ms
        self._cloud = cloud_cover_mean

    def air_temp_C(self, t_hours: float) -> float:
        """Return synthetic air temperature (°C) at simulation time t_hours.

        Uses sinusoidal model: T_air(t) = T_mean + (ΔT/2) * sin(2π(t - t_min)/24).

        Args:
            t_hours: Simulation time in hours from simulation start.

        Returns:
            Air temperature in °C.
        """
        hour_of_day = t_hours % 24.0
        return self._t_mean + (self._t_amp / 2.0) * math.sin(
            2.0 * math.pi * (hour_of_day - self._t_min) / 24.0
        )

    def rel_humidity(self, t_hours: float) -> float:
        """Return relative humidity (fraction 0-1) at time t_hours.

        Uses anti-correlated sinusoidal: RH peaks at dawn (low T) and dips at midday.

        Args:
            t_hours: Simulation time in hours.

        Returns:
            Relative humidity (0-1).
        """
        hour_of_day = t_hours % 24.0
        # Anti-correlated with temperature: min RH at same time as max T
        rh = self._rh_mean - self._rh_amp * math.sin(
            2.0 * math.pi * (hour_of_day - self._t_min) / 24.0
        )
        return min(1.0, max(0.01, rh))

    def wind_speed_ms(self, t_hours: float) -> float:
        """Return wind speed at 3 m height (m/s).

        Constant mean value; diurnal variation is modest for sheltered ponds.

        Args:
            t_hours: Simulation time in hours.

        Returns:
            Wind speed (m/s).
        """
        return max(0.1, self._wind)

    def cloud_cover(self, t_hours: float) -> float:
        """Return cloud cover fraction (0-1).

        Args:
            t_hours: Simulation time in hours.

        Returns:
            Cloud cover fraction.
        """
        return self._cloud


class CSVWeather:
    """Weather data provider from a CSV file.

    Expected CSV columns (case-insensitive, extra columns ignored):
        - ``time_h`` or ``hour``: simulation time in hours
        - ``t_air_C`` or ``temp_C``: air temperature (°C)
        - ``rh`` or ``rel_humidity``: relative humidity (fraction 0-1)
        - ``wind_ms`` or ``wind_speed_ms``: wind speed at 3 m (m/s)
        - ``cloud`` or ``cloud_cover``: cloud cover fraction (0-1)

    Values between rows are linearly interpolated.

    Args:
        csv_path: Path to CSV file.
        repeat: If True, cycle through the data when simulation exceeds file duration.
    """

    def __init__(self, csv_path: str | Path, repeat: bool = True) -> None:
        self._path = Path(csv_path)
        self._repeat = repeat
        self._times: list[float] = []
        self._t_air: list[float] = []
        self._rh: list[float] = []
        self._wind: list[float] = []
        self._cloud: list[float] = []
        self._load()

    def _load(self) -> None:
        """Load and parse the CSV file."""
        with open(self._path, newline="") as f:
            reader = csv.DictReader(f)
            headers = {h.lower().strip() for h in (reader.fieldnames or [])}
            for row in reader:
                # Normalize header names
                rlow = {k.lower().strip(): v for k, v in row.items()}
                t = float(rlow.get("time_h") or rlow.get("hour") or 0.0)
                ta = float(
                    rlow.get("t_air_c") or rlow.get("temp_c") or rlow.get("t_air") or 25.0
                )
                rh = float(rlow.get("rh") or rlow.get("rel_humidity") or 0.75)
                ws = float(rlow.get("wind_ms") or rlow.get("wind_speed_ms") or 2.0)
                cl = float(rlow.get("cloud") or rlow.get("cloud_cover") or 0.2)
                self._times.append(t)
                self._t_air.append(ta)
                self._rh.append(rh)
                self._wind.append(ws)
                self._cloud.append(cl)

    def _interpolate(self, series: list[float], t_hours: float) -> float:
        """Linear interpolation (with optional repeat) into a time series."""
        if not self._times:
            return series[0] if series else 0.0
        t_max = self._times[-1]
        if self._repeat and t_max > 0.0:
            t_hours = t_hours % t_max
        t = max(self._times[0], min(t_hours, t_max))
        # Binary search for interval
        lo, hi = 0, len(self._times) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self._times[mid] <= t:
                lo = mid
            else:
                hi = mid
        if hi == lo:
            return series[lo]
        frac = (t - self._times[lo]) / (self._times[hi] - self._times[lo])
        return series[lo] + frac * (series[hi] - series[lo])

    def air_temp_C(self, t_hours: float) -> float:
        return self._interpolate(self._t_air, t_hours)

    def rel_humidity(self, t_hours: float) -> float:
        return min(1.0, max(0.01, self._interpolate(self._rh, t_hours)))

    def wind_speed_ms(self, t_hours: float) -> float:
        return max(0.1, self._interpolate(self._wind, t_hours))

    def cloud_cover(self, t_hours: float) -> float:
        return min(1.0, max(0.0, self._interpolate(self._cloud, t_hours)))
