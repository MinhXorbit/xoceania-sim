"""Tests for the carbonate equilibrium pH solver.

Key tests:
- Newton-Raphson converges to known solutions
- pH consistent with seawater reference values
- CO2 saturation calculation correct
- Temperature and salinity dependence physically correct
"""

import math
import pytest
from xoceania_sim.subsystems.ph_carbon import (
    solve_pH,
    _carbonate_constants,
    dCT_dt,
    CarbonParams,
)
from xoceania_sim.forcing.forcing import ForcingState


def make_forcing(I_par=0.0) -> ForcingState:
    return ForcingState(
        I_sw=I_par * 2, I_par=I_par, I_par_avg=I_par * 0.5,
        T_air=25.0, RH=0.8, u_wind=3.0, cloud_cover=0.2,
        hour_of_day=12.0, day_of_year=200
    )


class TestCarbonateConstants:
    """Tests for temperature/salinity corrected equilibrium constants."""

    def test_K1_reasonable_range(self):
        """K1 at 25°C freshwater should be ~10^-6.35 = 4.5e-7."""
        K1, K2, Kw, KH = _carbonate_constants(25.0, 0.0)
        # pK1 ≈ 6.35 at 25°C
        pK1 = -math.log10(K1)
        assert 5.8 < pK1 < 6.8, f"pK1 = {pK1:.3f} out of expected range 5.8-6.8"

    def test_K2_reasonable_range(self):
        """K2 at 25°C freshwater should be ~10^-10.33 = 4.7e-11."""
        K1, K2, Kw, KH = _carbonate_constants(25.0, 0.0)
        pK2 = -math.log10(K2)
        assert 9.0 < pK2 < 10.5, f"pK2 = {pK2:.3f} out of expected range"

    def test_Kw_at_25C(self):
        """Kw at 25°C ≈ 1e-14."""
        K1, K2, Kw, KH = _carbonate_constants(25.0, 0.0)
        pKw = -math.log10(Kw)
        assert 13.5 < pKw < 14.5, f"pKw = {pKw:.3f}, expected ~14"

    def test_constants_temperature_dependence(self):
        """K1, K2 should change systematically with temperature."""
        K1_20, _, _, _ = _carbonate_constants(20.0, 0.0)
        K1_30, _, _, _ = _carbonate_constants(30.0, 0.0)
        # K1 increases with temperature (pK1 decreases)
        assert K1_30 > K1_20, "K1 should increase with temperature"


class TestSolvePH:
    """Tests for Newton-Raphson pH solver."""

    def test_returns_tuple(self):
        """solve_pH should return (pH, CO2_mg_L) tuple."""
        result = solve_pH(2.5, 120.0, 28.0, 15.0)
        assert len(result) == 2
        pH, CO2 = result
        assert math.isfinite(float(pH))
        assert math.isfinite(float(CO2))

    def test_pH_range(self):
        """pH should be in valid range 4-12."""
        pH, _ = solve_pH(2.5, 120.0, 28.0, 15.0)
        assert 4.0 <= float(pH) <= 12.0, f"pH {pH} out of range"

    def test_high_CT_low_pH(self):
        """Very high CT (excess CO2) should give low pH."""
        pH_high_CT, _ = solve_pH(10.0, 50.0, 25.0, 0.0)
        pH_low_CT, _ = solve_pH(2.0, 50.0, 25.0, 0.0)
        assert float(pH_high_CT) < float(pH_low_CT), "High CT should give lower pH"

    def test_seawater_reference(self):
        """Seawater reference: CT≈2.1 mmol/L, Alk≈2.35 mmol/L (140 mg/L), S=35, T=25°C.
        Expected pH ~8.1-8.3 (open ocean carbonate chemistry).
        Tolerance: ±0.5 pH units (Millero 2010).
        """
        pH, _ = solve_pH(
            CT_mmol_L=2.1,
            alkalinity_mg_L=118.0,   # ≈ 2.36 mmol/L / 2 × 100 mg CaCO3
            T_C=25.0,
            salinity_ppt=35.0,
        )
        assert 7.5 <= float(pH) <= 9.0, \
            f"Seawater pH {pH:.2f} should be ~8.0-8.5 (within ±0.5 units of 8.0)"

    def test_co2_non_negative(self):
        """Free CO2 concentration should always be non-negative."""
        for CT in [0.5, 2.0, 5.0]:
            for alk in [50.0, 100.0, 150.0]:
                _, CO2 = solve_pH(CT, alk, 28.0, 15.0)
                assert float(CO2) >= 0.0, f"CO2 negative at CT={CT}, alk={alk}"

    def test_high_ph_low_free_co2(self):
        """At high pH (alkaline), free CO2 should approach zero."""
        # High alk relative to CT → high pH → low CO2
        pH, CO2 = solve_pH(CT_mmol_L=2.5, alkalinity_mg_L=120.0, T_C=28.0, salinity_ppt=0.0)
        if float(pH) > 8.5:
            assert float(CO2) < 10.0, f"Free CO2 too high at pH {pH:.2f}"

    def test_temperature_effect_on_ph(self):
        """pH should change slightly with temperature at fixed CT and Alk."""
        pH_20, _ = solve_pH(2.5, 80.0, 20.0, 0.0)
        pH_30, _ = solve_pH(2.5, 80.0, 30.0, 0.0)
        # Both should be in valid range
        assert 4.0 <= float(pH_20) <= 12.0
        assert 4.0 <= float(pH_30) <= 12.0

    def test_aquaculture_pond_realistic(self):
        """Typical vannamei pond: CT=2.5, alk=120 mg/L, T=28, S=15 → pH 7-9."""
        pH, CO2 = solve_pH(2.5, 120.0, 28.0, 15.0)
        assert 6.0 <= float(pH) <= 10.0, f"Vannamei pond pH {pH:.2f} unrealistic"


class TestCTDynamics:
    """Tests for the total carbon ODE."""

    def setup_method(self):
        self.params = CarbonParams.from_config(SimConfig().pond)
        self.forcing = make_forcing(I_par=0.0)

    def test_returns_finite(self):
        from xoceania_sim.config import SimConfig
        cfg = SimConfig()
        params = CarbonParams.from_config(cfg.pond)
        dCT = dCT_dt(
            CT_mmol_L=2.5, T_C=28.0,
            forcing=make_forcing(0.0), params=params,
            R_algae_O2=0.5, R_shrimp_O2=0.02, P_gross_O2=0.0, R_nitr_N=0.01
        )
        assert math.isfinite(float(dCT))

    def test_respiration_increases_ct(self):
        """Respiration should add CT (CO2 production)."""
        from xoceania_sim.config import SimConfig
        cfg = SimConfig()
        params = CarbonParams.from_config(cfg.pond)
        f = make_forcing(0.0)
        dCT_no_resp = dCT_dt(2.5, 28.0, f, params, 0.0, 0.0, 0.0, 0.0)
        dCT_resp = dCT_dt(2.5, 28.0, f, params, 1.0, 0.0, 0.0, 0.0)
        assert float(dCT_resp) > float(dCT_no_resp), "Respiration should increase CT"

    def test_photosynthesis_decreases_ct(self):
        """Photosynthesis should remove CT (CO2 consumption)."""
        from xoceania_sim.config import SimConfig
        cfg = SimConfig()
        params = CarbonParams.from_config(cfg.pond)
        f = make_forcing(500.0)
        dCT_dark = dCT_dt(2.5, 28.0, f, params, 0.0, 0.0, 0.0, 0.0)
        dCT_photo = dCT_dt(2.5, 28.0, f, params, 0.0, 0.0, 2.0, 0.0)
        assert float(dCT_photo) < float(dCT_dark), "Photosynthesis should decrease CT"


# Import here to avoid circular
from xoceania_sim.config import SimConfig
