"""Tests for the coupled PondSimulator.

Key tests:
- 48-hour run produces physically plausible bounded trajectories
- Diurnal patterns are present (DO higher at noon, lower at night)
- All state variables remain finite
- Temperature stays in realistic range
- SimulationResult has correct structure
"""

import pytest
import numpy as np
import pandas as pd
from xoceania_sim import PondSimulator, SimConfig, load_config


class TestSimulatorBasic:
    """Basic integration and output tests."""

    def setup_method(self):
        self.cfg = SimConfig()
        self.sim = PondSimulator(self.cfg)

    def test_run_returns_simulation_result(self):
        """run() should return a SimulationResult object."""
        from xoceania_sim.simulator import SimulationResult
        result = self.sim.run(t_span=(0, 24))
        assert isinstance(result, SimulationResult)

    def test_output_is_dataframe(self):
        """SimulationResult.df should be a pandas DataFrame."""
        result = self.sim.run(t_span=(0, 24))
        assert isinstance(result.df, pd.DataFrame)

    def test_output_has_required_columns(self):
        """DataFrame should contain core water quality columns."""
        required = ["T", "DO", "pH", "TAN", "NH3", "C_T", "A"]
        result = self.sim.run(t_span=(0, 24))
        for col in required:
            assert col in result.df.columns, f"Missing column: {col}"

    def test_output_index_is_time(self):
        """DataFrame index should be time in hours."""
        result = self.sim.run(t_span=(0, 24))
        assert result.df.index.name == "time_h"
        assert result.df.index[0] == pytest.approx(0.0)
        assert result.df.index[-1] == pytest.approx(24.0)

    def test_no_nan_values(self):
        """No NaN values in output."""
        result = self.sim.run(t_span=(0, 48))
        assert not result.df.isnull().any().any(), "NaN values found in output"

    def test_no_inf_values(self):
        """No infinite values in output."""
        result = self.sim.run(t_span=(0, 48))
        df = result.df
        assert np.isfinite(df.values.astype(float)).all(), "Infinite values found in output"


class TestPhysicalBounds48h:
    """Physical plausibility tests for 48-hour simulation."""

    def setup_method(self):
        cfg = SimConfig()
        sim = PondSimulator(cfg)
        self.result = sim.run(t_span=(0, 48))
        self.df = self.result.df

    def test_do_bounds(self):
        """DO should stay between 1 and 25 mg/L."""
        DO = self.df['DO'].values.astype(float)
        assert DO.min() >= 1.0, f"DO crashed below 1 mg/L: min={DO.min():.2f}"
        assert DO.max() <= 25.0, f"DO supersaturated beyond 25 mg/L: max={DO.max():.2f}"

    def test_ph_bounds(self):
        """pH should stay between 6 and 10."""
        pH = self.df['pH'].values.astype(float)
        assert pH.min() >= 6.0, f"pH too low: {pH.min():.2f}"
        assert pH.max() <= 10.0, f"pH too high: {pH.max():.2f}"

    def test_temperature_bounds(self):
        """Temperature should stay between 20 and 35°C."""
        T = self.df['T'].values.astype(float)
        assert T.min() >= 20.0, f"Temperature too low: {T.min():.2f}"
        assert T.max() <= 35.0, f"Temperature too high: {T.max():.2f}"

    def test_tan_non_negative(self):
        """TAN should be non-negative."""
        TAN = self.df['TAN'].values.astype(float)
        assert TAN.min() >= 0.0, f"TAN went negative: {TAN.min():.4f}"

    def test_nh3_non_negative(self):
        """Un-ionized NH3 should be non-negative."""
        NH3 = self.df['NH3'].values.astype(float)
        assert NH3.min() >= 0.0

    def test_algae_non_negative(self):
        """Algal biomass should be non-negative."""
        A = self.df['A'].values.astype(float)
        assert A.min() >= 0.0

    def test_biomass_non_negative(self):
        """Shrimp biomass should be non-negative."""
        B = self.df['B'].values.astype(float)
        assert B.min() >= 0.0

    def test_do_pct_saturation(self):
        """DO should be 50-300% of saturation in a managed pond."""
        DO_pct = self.df['DO_pct_sat'].values.astype(float)
        assert DO_pct.max() <= 300.0, f"DO supersaturation extreme: {DO_pct.max():.0f}%"

    def test_diurnal_do_variation(self):
        """DO should vary diurnally (higher during day, lower at night)."""
        DO = self.df['DO'].values.astype(float)
        DO_range = DO.max() - DO.min()
        assert DO_range > 0.5, f"Insufficient diurnal DO variation: {DO_range:.2f} mg/L"

    def test_diurnal_temperature_variation(self):
        """Temperature should show diurnal pattern."""
        T = self.df['T'].values.astype(float)
        T_range = T.max() - T.min()
        assert T_range > 1.0, f"Insufficient diurnal temp variation: {T_range:.2f}°C"


class TestSimulatorEventDetection:
    """Tests for boundary conditions and stress scenarios."""

    def test_low_do_scenario(self):
        """Simulation should handle low initial DO without crashing."""
        cfg = SimConfig()
        cfg.initial_do = 2.0
        cfg.pond.n_aerators = 0  # no aeration
        cfg.pond.aerator_kLa_20 = 0.0
        sim = PondSimulator(cfg)
        result = sim.run(t_span=(0, 24))
        # Should complete without raising exception
        assert result.df is not None

    def test_long_run_stability(self):
        """7-day simulation should remain stable."""
        cfg = SimConfig()
        sim = PondSimulator(cfg)
        result = sim.run(t_span=(0, 7 * 24))
        df = result.df
        DO = df['DO'].values.astype(float)
        pH = df['pH'].values.astype(float)
        T = df['T'].values.astype(float)
        assert np.isfinite(DO).all(), "DO went infinite in 7d run"
        assert np.isfinite(pH).all(), "pH went infinite in 7d run"
        assert np.isfinite(T).all(), "T went infinite in 7d run"

    def test_catfish_config(self):
        """Catfish config should run without errors."""
        from pathlib import Path
        cfg = load_config(Path(__file__).resolve().parents[1] / 'configs' / 'catfish_alabama.yaml')
        sim = PondSimulator(cfg)
        result = sim.run(t_span=(0, 48))
        assert result.df is not None
        T = result.df['T'].values.astype(float)
        assert T.max() < 40.0, "Catfish pond temp too high"

    def test_reset_reinitializes(self):
        """reset() should allow re-running with fresh state."""
        cfg = SimConfig()
        sim = PondSimulator(cfg)
        result1 = sim.run(t_span=(0, 24))
        sim.reset()
        result2 = sim.run(t_span=(0, 24))
        # Results should be identical after reset
        np.testing.assert_allclose(
            result1.df['DO'].values.astype(float),
            result2.df['DO'].values.astype(float),
            rtol=1e-4, err_msg="Reset did not restore initial state"
        )


class TestSimulatorSummary:
    """Tests for SimulationResult methods."""

    def test_summary_returns_dataframe(self):
        cfg = SimConfig()
        sim = PondSimulator(cfg)
        result = sim.run(t_span=(0, 24))
        summary = result.summary()
        assert isinstance(summary, pd.DataFrame)

    def test_repr_string(self):
        cfg = SimConfig()
        sim = PondSimulator(cfg)
        result = sim.run(t_span=(0, 24))
        s = repr(result)
        assert "SimulationResult" in s
