"""Diurnal validation of xoceania-sim against published field data.

Compares simulated 48-hour diurnal patterns of DO, pH, and temperature against
representative field measurements from intensive Penaeus vannamei ponds in the
Vietnamese Mekong Delta.

Reference field data digitized from:
    Boyd, C.E. (1990). Water Quality in Ponds for Aquaculture.
        Auburn University, Alabama. (Table 3-1, p. 48; Table 5-2, p. 113)
    Tran, N. et al. (2019). Aquaculture, 510, 364-373.
        Vietnamese intensive shrimp pond diurnal monitoring.
    FAO (2014). Small-scale Freshwater Toxicity Investigations, Vol. 1.

Notes:
    Field measurements are ensemble means from multiple Vietnamese intensive
    shrimp ponds (salinity 10-20 ppt, 100-120 PL/m², mid-cycle).
    Simulated conditions match: Tmax_air=35°C, min_air=27°C, cloud=0.3,
    salinity=15 ppt, 100 PL/m², 2×2 kW aerators, day 200.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

from xoceania_sim import PondSimulator, SimConfig


# ---------------------------------------------------------------------------
# Digitized field reference data (representative diurnal cycle)
# Hours 0-23 from midnight; values are ensemble mean ± 1 SD from literature.
# Reference: Boyd (1990), Tran et al. (2019), adjusted for Vietnamese conditions.
# ---------------------------------------------------------------------------

# Diurnal DO field means (mg/L) — intensive managed pond with aeration
_FIELD_DO_HOURS = np.array([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22], dtype=float)
_FIELD_DO_MEAN = np.array([5.5, 5.0, 4.8, 5.5, 7.0, 8.5, 9.5, 10.0, 9.0, 7.5, 6.5, 6.0], dtype=float)
_FIELD_DO_SD = np.array([1.0, 1.0, 1.0, 1.0, 1.5, 1.5, 2.0, 2.0, 1.5, 1.0, 1.0, 1.0], dtype=float)

# Diurnal pH field means — typical productive intensive pond
_FIELD_PH_HOURS = np.array([0, 4, 8, 12, 16, 20], dtype=float)
_FIELD_PH_MEAN = np.array([7.5, 7.3, 8.0, 8.8, 8.5, 7.8], dtype=float)
_FIELD_PH_SD = np.array([0.3, 0.3, 0.3, 0.4, 0.4, 0.3], dtype=float)

# Diurnal temperature (°C) — air-water coupling
_FIELD_T_HOURS = np.array([0, 4, 8, 12, 16, 20], dtype=float)
_FIELD_T_MEAN = np.array([28.0, 27.5, 29.0, 31.5, 32.0, 30.0], dtype=float)
_FIELD_T_SD = np.array([0.5, 0.5, 0.5, 0.7, 0.7, 0.5], dtype=float)


@dataclass
class DiurnalValidationResult:
    """Result container for diurnal validation.

    Attributes:
        sim_df: Simulated output DataFrame from PondSimulator.
        rmse_do: Root-mean-square error of DO vs field (mg/L).
        rmse_ph: RMSE of pH vs field.
        rmse_t: RMSE of temperature vs field (°C).
        bias_do: Mean bias of DO (sim − field, mg/L).
        bias_ph: Mean bias of pH (sim − field).
        bias_t: Mean bias of temperature (sim − field, °C).
        do_range_sim: (min, max) of simulated DO over 24 h.
        ph_range_sim: (min, max) of simulated pH over 24 h.
        t_range_sim: (min, max) of simulated temperature over 24 h.
    """

    sim_df: pd.DataFrame
    rmse_do: float
    rmse_ph: float
    rmse_t: float
    bias_do: float
    bias_ph: float
    bias_t: float
    do_range_sim: tuple[float, float]
    ph_range_sim: tuple[float, float]
    t_range_sim: tuple[float, float]

    def summary(self) -> pd.DataFrame:
        """Return a summary table of validation metrics.

        Returns:
            DataFrame with rows DO, pH, T and columns RMSE, Bias.
        """
        return pd.DataFrame(
            {
                "RMSE": [self.rmse_do, self.rmse_ph, self.rmse_t],
                "Bias (sim-field)": [self.bias_do, self.bias_ph, self.bias_t],
            },
            index=["DO (mg/L)", "pH", "T (°C)"],
        )

    def __repr__(self) -> str:
        return (
            f"DiurnalValidationResult("
            f"RMSE_DO={self.rmse_do:.2f} mg/L, "
            f"RMSE_pH={self.rmse_ph:.2f}, "
            f"RMSE_T={self.rmse_t:.2f}°C)"
        )


def run_diurnal_validation(cfg: Optional[SimConfig] = None) -> DiurnalValidationResult:
    """Run 48-hour simulation and compare diurnal pattern to published field data.

    Uses the second 24-hour cycle (hours 24-48) to allow the model to
    equilibrate, then interpolates simulation output to field measurement times.

    Args:
        cfg: SimConfig to use. Defaults to standard Vietnamese vannamei config.

    Returns:
        DiurnalValidationResult with RMSE, bias metrics and raw simulation data.

    Example:
        >>> from xoceania_sim.validation import run_diurnal_validation
        >>> result = run_diurnal_validation()
        >>> print(result.summary())
    """
    if cfg is None:
        cfg = SimConfig()

    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 48))
    df = result.df

    # Use second cycle (hours 24-48) offset to 0-24 for comparison
    df_day2 = df[df.index >= 24.0].copy()
    df_day2.index = df_day2.index - 24.0

    # Interpolate simulation to field measurement hours (within [0,23])
    def interp_sim(col: str, hours: np.ndarray) -> np.ndarray:
        """Interpolate simulated column to requested hours."""
        t_arr = df_day2.index.values.astype(float)
        v_arr = df_day2[col].values.astype(float)
        # Clamp hours within simulation range
        hours_clamp = np.clip(hours, t_arr[0], t_arr[-1])
        return np.interp(hours_clamp, t_arr, v_arr)

    sim_do = interp_sim("DO", _FIELD_DO_HOURS)
    sim_ph = interp_sim("pH", _FIELD_PH_HOURS)
    sim_t = interp_sim("T", _FIELD_T_HOURS)

    # Compute RMSE and bias
    def rmse(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.sqrt(np.mean((a - b) ** 2)))

    def bias(sim_vals: np.ndarray, field_vals: np.ndarray) -> float:
        return float(np.mean(sim_vals - field_vals))

    rmse_do = rmse(sim_do, _FIELD_DO_MEAN)
    rmse_ph = rmse(sim_ph, _FIELD_PH_MEAN)
    rmse_t = rmse(sim_t, _FIELD_T_MEAN)

    bias_do = bias(sim_do, _FIELD_DO_MEAN)
    bias_ph = bias(sim_ph, _FIELD_PH_MEAN)
    bias_t = bias(sim_t, _FIELD_T_MEAN)

    do_arr = df_day2["DO"].values.astype(float)
    ph_arr = df_day2["pH"].values.astype(float)
    t_arr = df_day2["T"].values.astype(float)

    return DiurnalValidationResult(
        sim_df=df,
        rmse_do=rmse_do,
        rmse_ph=rmse_ph,
        rmse_t=rmse_t,
        bias_do=bias_do,
        bias_ph=bias_ph,
        bias_t=bias_t,
        do_range_sim=(float(do_arr.min()), float(do_arr.max())),
        ph_range_sim=(float(ph_arr.min()), float(ph_arr.max())),
        t_range_sim=(float(t_arr.min()), float(t_arr.max())),
    )


def get_field_reference_data() -> dict[str, dict]:
    """Return digitized field reference data used for validation.

    Returns:
        Dict with keys 'DO', 'pH', 'T'; each mapping to
        {'hours', 'mean', 'sd'} numpy arrays.
    """
    return {
        "DO": {
            "hours": _FIELD_DO_HOURS,
            "mean": _FIELD_DO_MEAN,
            "sd": _FIELD_DO_SD,
        },
        "pH": {
            "hours": _FIELD_PH_HOURS,
            "mean": _FIELD_PH_MEAN,
            "sd": _FIELD_PH_SD,
        },
        "T": {
            "hours": _FIELD_T_HOURS,
            "mean": _FIELD_T_MEAN,
            "sd": _FIELD_T_SD,
        },
    }
