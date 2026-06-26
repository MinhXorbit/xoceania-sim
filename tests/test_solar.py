"""Tests for the Bird-Hulstrom solar irradiance model.

Verifies:
- Noon irradiance is positive
- Midnight irradiance is zero
- Daily integration gives plausible MJ/m²
- Cloud correction reduces irradiance
- PAR is 47% of shortwave
"""

import math
import pytest
from xoceania_sim.forcing.solar import (
    bird_hulstrom_irradiance,
    clear_sky_irradiance,
    par_underwater,
    kasten_czeplak_correction,
)


# Reference location: Ca Mau, Vietnam (9.5°N, 105°E)
LAT = 9.5
LON = 105.0
DOY = 200  # July, high solar angle in tropics


class TestBirdHulstrom:
    """Tests for Bird-Hulstrom clear-sky model."""

    def test_noon_irradiance_positive(self):
        """Solar noon irradiance must be positive."""
        I_dir, I_dif, I_glo = bird_hulstrom_irradiance(LAT, LON, DOY, hour_utc=5.0)
        assert I_glo > 0, f"Global irradiance at noon should be positive, got {I_glo}"
        assert I_dir >= 0, "Direct irradiance must be non-negative"
        assert I_dif >= 0, "Diffuse irradiance must be non-negative"

    def test_midnight_irradiance_zero(self):
        """Irradiance at solar midnight should be zero."""
        # UTC midnight ≈ solar midnight at LON=105 (UTC+7)
        I_dir, I_dif, I_glo = bird_hulstrom_irradiance(LAT, LON, DOY, hour_utc=17.0)  # 00:00 local
        assert I_glo == 0.0, f"Midnight irradiance should be 0, got {I_glo}"

    def test_reasonable_peak_irradiance(self):
        """Noon clear-sky irradiance should be 600-1100 W/m² at tropical site."""
        I_dir, I_dif, I_glo = bird_hulstrom_irradiance(LAT, LON, DOY, hour_utc=5.0)  # noon local
        assert 500 < I_glo < 1200, f"Peak irradiance out of range: {I_glo} W/m²"

    def test_daily_integration(self):
        """Daily solar energy integral should be in reasonable range (5-30 MJ/m²/day)."""
        # Integrate over 24 hours at 1-hour resolution
        daily_sum = 0.0
        for h in range(24):
            hour_utc = (h - 7) % 24  # local to UTC
            _, _, I_glo = bird_hulstrom_irradiance(LAT, LON, DOY, hour_utc=hour_utc)
            daily_sum += I_glo * 3600  # W/m² * 3600 s/h → J/m²
        daily_MJ = daily_sum / 1e6
        assert 5 < daily_MJ < 30, f"Daily solar energy {daily_MJ:.1f} MJ/m² out of range"

    def test_diffuse_less_than_global(self):
        """Diffuse irradiance should always be ≤ global irradiance."""
        for h_local in [6, 9, 12, 15, 18]:
            hour_utc = (h_local - 7) % 24
            I_dir, I_dif, I_glo = bird_hulstrom_irradiance(LAT, LON, DOY, hour_utc=hour_utc)
            if I_glo > 0:
                assert I_dif <= I_glo + 1e-6, f"Diffuse > global at h={h_local}"

    def test_direct_plus_diffuse_equals_global(self):
        """Global = direct + diffuse (within numerical tolerance)."""
        I_dir, I_dif, I_glo = bird_hulstrom_irradiance(LAT, LON, DOY, hour_utc=5.0)
        assert abs((I_dir + I_dif) - I_glo) < 10.0, "Global ≠ direct + diffuse"


class TestCloudCorrection:
    """Tests for Kasten-Czeplak cloud correction."""

    def test_clear_sky_no_change(self):
        """Zero cloud cover should not change irradiance."""
        I_clear = 800.0
        I_corr = kasten_czeplak_correction(I_clear, cloud_cover=0.0)
        assert abs(I_corr - I_clear) < 1e-6

    def test_overcast_reduces_irradiance(self):
        """Full overcast should significantly reduce irradiance."""
        I_clear = 800.0
        I_corr = kasten_czeplak_correction(I_clear, cloud_cover=1.0)
        assert I_corr < I_clear * 0.5, "Overcast should reduce to <50% of clear-sky"

    def test_partial_cloud_monotonic(self):
        """More cloud cover → lower irradiance (monotonic)."""
        I_clear = 800.0
        values = [kasten_czeplak_correction(I_clear, c) for c in [0.0, 0.2, 0.5, 0.8, 1.0]]
        for i in range(len(values) - 1):
            assert values[i] >= values[i + 1], "Cloud correction not monotonic"

    def test_par_fraction(self):
        """PAR should be 0.47 × global (Morel & Smith 1974)."""
        sol = clear_sky_irradiance(LAT, LON, DOY, hour_utc=5.0, cloud_cover=0.0)
        assert abs(sol.I_par - 0.47 * sol.I_global) < 1e-3, "PAR fraction wrong"


class TestBeerLambertPAR:
    """Tests for underwater PAR attenuation."""

    def test_surface_value_unchanged_at_zero_depth(self):
        """At zero effective depth, underwater PAR = surface PAR."""
        I = par_underwater(100.0, depth_m=0.001, k_d=1.0)
        assert abs(I - 100.0) < 1.0

    def test_attenuation_with_depth(self):
        """PAR should decrease with depth."""
        I1 = par_underwater(100.0, depth_m=0.5, k_d=2.0)
        I2 = par_underwater(100.0, depth_m=1.5, k_d=2.0)
        assert I1 > I2, "PAR should decrease with depth"

    def test_high_extinction(self):
        """High extinction coefficient should strongly attenuate PAR."""
        I = par_underwater(500.0, depth_m=1.5, k_d=5.0)
        assert I < 500.0 * 0.3, f"Very turbid pond (k_d=5) should attenuate >70% of PAR, got {I:.1f}"
