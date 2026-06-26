"""Tests for individual ODE subsystem modules.

Each ODE function is tested for:
- Returns finite values at known states
- Correct sign of derivatives
- Physical plausibility of rates
"""

import math
import pytest
import numpy as np

from xoceania_sim.config import SimConfig
from xoceania_sim.forcing.forcing import EnvironmentalForcing, ForcingState, create_forcing
from xoceania_sim.subsystems.temperature import TemperatureParams, dT_dt
from xoceania_sim.subsystems.dissolved_oxygen import DOParams, dDO_dt, do_saturation
from xoceania_sim.subsystems.ph_carbon import CarbonParams, dCT_dt, solve_pH
from xoceania_sim.subsystems.nitrogen import NitrogenParams, dTAN_dt, nh3_fraction
from xoceania_sim.subsystems.phytoplankton import PhytoplanktonParams, dA_dt
from xoceania_sim.subsystems.shrimp import ShrimpParams, ShrimpState, update_shrimp


# Standard conditions for tests
CFG = SimConfig()
FORCING = create_forcing(CFG.pond, CFG.weather)
F_NOON = FORCING.at(12.0)      # daytime
F_MIDNIGHT = FORCING.at(0.0)   # nighttime


class TestTemperatureSubsystem:
    """Tests for pond thermal energy balance ODE."""

    def setup_method(self):
        self.params = TemperatureParams.from_pond_config(CFG.pond)

    def test_returns_finite(self):
        dT = dT_dt(28.0, F_NOON, self.params)
        assert math.isfinite(float(dT)), "dT_dt should return finite value"

    def test_daytime_warming(self):
        """At solar noon, pond should warm."""
        dT = dT_dt(25.0, F_NOON, self.params)
        assert float(dT) > 0, f"Pond should warm at noon, got dT={dT:.4f}"

    def test_nighttime_cooling(self):
        """At midnight with no solar input, pond should cool."""
        dT = dT_dt(30.0, F_MIDNIGHT, self.params)
        assert float(dT) < 0, f"Pond should cool at midnight, got dT={dT:.4f}"

    def test_reasonable_rate_magnitude(self):
        """Temperature change should be < 2°C/h under normal conditions."""
        dT = dT_dt(28.0, F_NOON, self.params)
        assert abs(float(dT)) < 2.0, f"|dT/dt| too large: {abs(dT):.2f} °C/h"

    def test_hot_pond_cools(self):
        """Pond significantly hotter than air should cool."""
        dT = dT_dt(40.0, F_MIDNIGHT, self.params)
        assert float(dT) < 0, "Very hot pond at night should cool"


class TestDOSubsystem:
    """Tests for dissolved oxygen mass-balance ODE."""

    def setup_method(self):
        self.params = DOParams.from_config(CFG.pond)

    def test_saturation_freshwater(self):
        """DO saturation at 20°C freshwater should be ~9.1 mg/L."""
        DO_sat = do_saturation(20.0, 0.0)
        assert abs(float(DO_sat) - 9.1) < 0.5, f"DO sat mismatch: {DO_sat:.2f}"

    def test_saturation_temperature_dependence(self):
        """DO saturation should decrease with temperature."""
        DO_25 = do_saturation(25.0, 0.0)
        DO_30 = do_saturation(30.0, 0.0)
        assert float(DO_25) > float(DO_30), "DO_sat should decrease with T"

    def test_saturation_salinity_correction(self):
        """Saline water should have lower DO saturation than fresh."""
        DO_fresh = do_saturation(28.0, 0.0)
        DO_saline = do_saturation(28.0, 15.0)
        assert float(DO_fresh) > float(DO_saline), "Saline DO_sat should be lower"

    def test_returns_finite(self):
        dDO = dDO_dt(7.0, 28.0, F_NOON, self.params,
                     P_gross=2.0, R_algae=0.5, R_shrimp=0.02, R_nitr=0.01)
        assert math.isfinite(float(dDO)), "dDO_dt should return finite value"

    def test_reaeration_positive_below_saturation(self):
        """When DO < DO_sat, reaeration should add DO."""
        # Very low DO, no other terms
        dDO = dDO_dt(1.0, 28.0, F_MIDNIGHT, self.params,
                     P_gross=0.0, R_algae=0.0, R_shrimp=0.0, R_nitr=0.0)
        assert float(dDO) > 0, "Reaeration should increase DO when undersaturated"

    def test_supersaturation_outgassing(self):
        """When DO >> DO_sat, reaeration should remove DO."""
        dDO = dDO_dt(20.0, 28.0, F_MIDNIGHT, self.params,
                     P_gross=0.0, R_algae=0.0, R_shrimp=0.0, R_nitr=0.0)
        # Reaeration term is negative (outgassing); SOD is also negative
        assert float(dDO) < 0, "Reaeration should decrease DO when supersaturated"

    def test_photosynthesis_increases_do(self):
        """High gross photosynthesis should increase DO."""
        dDO_dark = dDO_dt(7.0, 28.0, F_NOON, self.params,
                          P_gross=0.0, R_algae=0.0, R_shrimp=0.0, R_nitr=0.0)
        dDO_light = dDO_dt(7.0, 28.0, F_NOON, self.params,
                           P_gross=5.0, R_algae=0.0, R_shrimp=0.0, R_nitr=0.0)
        assert float(dDO_light) > float(dDO_dark), "Photosynthesis should increase DO"


class TestNitrogenSubsystem:
    """Tests for TAN dynamics ODE."""

    def setup_method(self):
        self.params = NitrogenParams.from_config(CFG.pond)

    def test_nh3_fraction_increases_with_pH(self):
        """NH₃ fraction should increase with pH (Emerson 1975)."""
        f7 = nh3_fraction(7.0, 28.0)
        f8 = nh3_fraction(8.0, 28.0)
        f9 = nh3_fraction(9.0, 28.0)
        assert float(f7) < float(f8) < float(f9), "NH3 fraction should increase with pH"

    def test_nh3_fraction_increases_with_temperature(self):
        """NH₃ fraction should increase with temperature."""
        f25 = nh3_fraction(8.0, 25.0)
        f30 = nh3_fraction(8.0, 30.0)
        assert float(f25) < float(f30), "NH3 fraction should increase with T"

    def test_nh3_fraction_range(self):
        """NH₃ fraction should be 0-1."""
        f = nh3_fraction(7.5, 28.0)
        assert 0 <= float(f) <= 1.0, f"NH3 fraction out of range: {f}"

    def test_returns_finite(self):
        dTAN, R_nitr = dTAN_dt(
            0.5, 7.0, 28.0, 8.0, F_NOON, self.params,
            E_shrimp=0.01, A_chl=50.0
        )
        assert math.isfinite(float(dTAN)), "dTAN_dt should be finite"
        assert math.isfinite(float(R_nitr)), "Nitrification rate should be finite"

    def test_nitrification_zero_at_low_do(self):
        """Nitrification should approach zero when DO → 0."""
        _, R_nitr_low = dTAN_dt(
            1.0, 0.01, 28.0, 7.0, F_NOON, self.params, 0.0, 0.0
        )
        _, R_nitr_high = dTAN_dt(
            1.0, 7.0, 28.0, 7.0, F_NOON, self.params, 0.0, 0.0
        )
        assert float(R_nitr_low) < float(R_nitr_high) * 0.1, \
            "Nitrification should be near zero at DO<0.1"

    def test_excretion_increases_tan(self):
        """Positive shrimp excretion should drive TAN increase."""
        dTAN_no_excr, _ = dTAN_dt(0.1, 7.0, 28.0, 7.5, F_NOON, self.params, 0.0, 0.0)
        dTAN_excr, _ = dTAN_dt(0.1, 7.0, 28.0, 7.5, F_NOON, self.params, 1.0, 0.0)
        assert float(dTAN_excr) > float(dTAN_no_excr), "Excretion should increase TAN"


class TestPhytoplanktonSubsystem:
    """Tests for phytoplankton biomass ODE."""

    def setup_method(self):
        self.params = PhytoplanktonParams.from_config(CFG.pond)

    def test_returns_three_values(self):
        result = dA_dt(100.0, 28.0, 0.5, F_NOON, self.params)
        assert len(result) == 3, "dA_dt should return (dA, P_gross, R_algae)"

    def test_photosynthesis_zero_at_night(self):
        """Gross photosynthesis should be zero at midnight."""
        _, P_gross, _ = dA_dt(100.0, 28.0, 0.5, F_MIDNIGHT, self.params)
        assert float(P_gross) < 0.001, "P_gross should be ~0 at midnight"

    def test_photosynthesis_positive_at_noon(self):
        """Gross photosynthesis should be positive at noon."""
        _, P_gross, _ = dA_dt(100.0, 28.0, 0.5, F_NOON, self.params)
        assert float(P_gross) > 0.0, "P_gross should be >0 at noon"

    def test_respiration_positive(self):
        """Algal respiration should always be non-negative."""
        for f in [F_NOON, F_MIDNIGHT]:
            _, _, R_algae = dA_dt(100.0, 28.0, 0.5, f, self.params)
            assert float(R_algae) >= 0.0, "R_algae should be non-negative"

    def test_returns_finite(self):
        dA, P, R = dA_dt(50.0, 28.0, 0.5, F_NOON, self.params)
        assert math.isfinite(float(dA))
        assert math.isfinite(float(P))
        assert math.isfinite(float(R))

    def test_growth_increases_with_light(self):
        """Net growth should be higher at noon than midnight."""
        dA_noon, _, _ = dA_dt(100.0, 28.0, 1.0, F_NOON, self.params)
        dA_night, _, _ = dA_dt(100.0, 28.0, 1.0, F_MIDNIGHT, self.params)
        assert float(dA_noon) > float(dA_night), "Growth higher at noon"

    def test_zero_biomass_zero_change(self):
        """At zero biomass, dA should be zero or near zero."""
        dA, P, R = dA_dt(0.0, 28.0, 0.5, F_NOON, self.params)
        assert abs(float(dA)) < 1e-10, "dA at A=0 should be ~0"


class TestShrimpSubsystem:
    """Tests for Penaeus vannamei shrimp module."""

    def setup_method(self):
        self.params = ShrimpParams.from_config(CFG.shrimp)
        self.state = ShrimpState(W_g=5.0, B_g_m2=500.0, survival=1.0)

    def test_returns_valid_state(self):
        new_state, R_o2, E_tan, mort = update_shrimp(
            self.state, 28.0, 7.0, 0.01, 1.0, self.params
        )
        assert isinstance(new_state, ShrimpState)
        assert new_state.W_g > 0
        assert new_state.B_g_m2 >= 0
        assert 0 <= new_state.survival <= 1.0

    def test_respiration_positive(self):
        _, R_o2, _, _ = update_shrimp(self.state, 28.0, 7.0, 0.0, 1.0, self.params)
        assert float(R_o2) >= 0, "Shrimp O2 demand should be non-negative"

    def test_excretion_positive(self):
        _, _, E_tan, _ = update_shrimp(self.state, 28.0, 7.0, 0.0, 1.0, self.params)
        assert float(E_tan) >= 0, "TAN excretion should be non-negative"

    def test_growth_positive_at_good_conditions(self):
        """Shrimp weight should increase under good conditions."""
        new_state, _, _, _ = update_shrimp(
            self.state, 28.0, 7.0, 0.0, 24.0, self.params
        )
        assert new_state.W_g > self.state.W_g, "Shrimp should grow in 24h"

    def test_mortality_increases_at_low_do(self):
        """Stress mortality should increase at low DO."""
        _, _, _, mort_low_do = update_shrimp(self.state, 28.0, 1.0, 0.0, 1.0, self.params)
        _, _, _, mort_high_do = update_shrimp(self.state, 28.0, 7.0, 0.0, 1.0, self.params)
        assert float(mort_low_do) > float(mort_high_do), "Stress mortality at DO=1 > DO=7"

    def test_survival_decreases_with_stress(self):
        """Prolonged low DO should decrease survival."""
        state = ShrimpState(W_g=5.0, B_g_m2=500.0, survival=1.0)
        for _ in range(24):  # 24h of stress
            state, _, _, _ = update_shrimp(state, 28.0, 0.5, 0.5, 1.0, self.params)
        assert state.survival < 1.0, "Survival should decrease under 24h of stress"
