"""One-at-a-time (OAT) sensitivity analysis for xoceania-sim.

Perturbs each key parameter ±20% from its baseline value and measures the
change in simulation outputs (DO mean, pH mean, TAN mean, T mean over 48 h).

This is a local, OAT approach following standard practice for mechanistic
aquaculture models (Piedrahita, 1990; Teichert-Coddington & Green, 1993).

References:
    Piedrahita, R.H. (1990). Calibration and validation of a pond water
        quality model. Aquaculture Research, 21(1), 69-81.
    Teichert-Coddington, D.R., & Green, B.W. (1993). Tilapia growth
        improvement by periodic draining. Aquaculture, 116, 281-289.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd

from xoceania_sim import PondSimulator, SimConfig


# Parameters to perturb and their path/setter functions
# Each entry: (label, getter, setter) where getter/setter operate on SimConfig
_PARAM_DEFS: list[tuple[str, Callable, Callable]] = [
    (
        "aerator_kLa_20",
        lambda c: c.pond.aerator_kLa_20,
        lambda c, v: setattr(c.pond, "aerator_kLa_20", v),
    ),
    (
        "n_aerators",
        lambda c: c.pond.n_aerators,
        lambda c, v: setattr(c.pond, "n_aerators", v),
    ),
    (
        "depth_m",
        lambda c: c.pond.depth_m,
        lambda c, v: setattr(c.pond, "depth_m", v),
    ),
    (
        "salinity_ppt",
        lambda c: c.pond.salinity_ppt,
        lambda c, v: setattr(c.pond, "salinity_ppt", v),
    ),
    (
        "alkalinity_mg_L",
        lambda c: c.pond.alkalinity_mg_L,
        lambda c, v: setattr(c.pond, "alkalinity_mg_L", v),
    ),
    (
        "sod_g_m2_d",
        lambda c: c.pond.sod_g_m2_d,
        lambda c, v: setattr(c.pond, "sod_g_m2_d", v),
    ),
    (
        "stocking_density_m2",
        lambda c: c.shrimp.stocking_density_m2,
        lambda c, v: setattr(c.shrimp, "stocking_density_m2", v),
    ),
    (
        "fcr",
        lambda c: c.shrimp.fcr,
        lambda c, v: setattr(c.shrimp, "fcr", v),
    ),
    (
        "t_mean_C",
        lambda c: c.weather.t_mean_C,
        lambda c, v: setattr(c.weather, "t_mean_C", v),
    ),
    (
        "cloud_cover",
        lambda c: c.weather.cloud_cover,
        lambda c, v: setattr(c.weather, "cloud_cover", v),
    ),
]


@dataclass
class SensitivityResult:
    """Result container for OAT sensitivity analysis.

    Attributes:
        table: DataFrame with parameters as rows, output metrics as columns.
            Values are percent change relative to baseline.
        baseline: Dict of baseline output metrics.
    """

    table: pd.DataFrame
    baseline: dict[str, float]

    def top_n(self, output: str, n: int = 5) -> pd.Series:
        """Return top-N most sensitive parameters for a given output metric.

        Args:
            output: Output column name (e.g., 'DO_mean_pct').
            n: Number of top parameters to return.

        Returns:
            Series with parameter names as index and sensitivity values.
        """
        col = self.table[output].abs().sort_values(ascending=False)
        return col.head(n)

    def __repr__(self) -> str:
        return f"SensitivityResult(n_params={len(self.table)}, baseline={self.baseline})"


def _run_sim_metrics(cfg: SimConfig, t_span: tuple[float, float] = (0, 48)) -> dict[str, float]:
    """Run simulation and return key output metrics.

    Args:
        cfg: SimConfig to simulate.
        t_span: Simulation span in hours.

    Returns:
        Dict with keys: DO_mean, DO_min, pH_mean, TAN_mean, T_mean.
    """
    sim = PondSimulator(cfg)
    result = sim.run(t_span=t_span)
    df = result.df
    return {
        "DO_mean": float(df["DO"].mean()),
        "DO_min": float(df["DO"].min()),
        "pH_mean": float(df["pH"].mean()),
        "TAN_mean": float(df["TAN"].mean()),
        "T_mean": float(df["T"].mean()),
    }


def run_sensitivity_analysis(
    base_cfg: Optional[SimConfig] = None,
    perturbation: float = 0.20,
    t_span: tuple[float, float] = (0, 48),
) -> SensitivityResult:
    """Run OAT sensitivity analysis across key model parameters.

    For each parameter, runs two simulations (±perturbation from baseline)
    and computes the normalized sensitivity index:
        S = (ΔY / Y_base) / (ΔX / X_base) * 100  [% change in Y per % change in X]

    Args:
        base_cfg: Baseline SimConfig. Defaults to standard Vietnamese vannamei config.
        perturbation: Fractional perturbation (default 0.20 = ±20%).
        t_span: Simulation time span in hours (default 48 h).

    Returns:
        SensitivityResult with table of sensitivity indices and baseline metrics.

    Example:
        >>> from xoceania_sim.validation import run_sensitivity_analysis
        >>> result = run_sensitivity_analysis()
        >>> print(result.table.round(2))
        >>> print(result.top_n('DO_mean'))
    """
    if base_cfg is None:
        base_cfg = SimConfig()

    baseline_metrics = _run_sim_metrics(base_cfg, t_span)

    rows = []
    for label, getter, setter in _PARAM_DEFS:
        x_base = getter(base_cfg)
        if x_base == 0.0:
            continue

        row = {"parameter": label}

        for sign, tag in [(+1, "plus"), (-1, "minus")]:
            cfg_perturbed = copy.deepcopy(base_cfg)
            x_new = x_base * (1.0 + sign * perturbation)
            setter(cfg_perturbed, x_new)

            try:
                metrics = _run_sim_metrics(cfg_perturbed, t_span)
                for key, y_base in baseline_metrics.items():
                    if y_base == 0.0:
                        si = 0.0
                    else:
                        delta_y_pct = (metrics[key] - y_base) / abs(y_base) * 100.0
                        delta_x_pct = sign * perturbation * 100.0
                        si = delta_y_pct / delta_x_pct * 100.0  # sensitivity index
                    row[f"{key}_{tag}"] = round(si, 3)
            except Exception:
                for key in baseline_metrics:
                    row[f"{key}_{tag}"] = float("nan")

        # Mean absolute sensitivity across + and - directions
        for key in baseline_metrics:
            plus_val = row.get(f"{key}_plus", float("nan"))
            minus_val = row.get(f"{key}_minus", float("nan"))
            if np.isfinite(plus_val) and np.isfinite(minus_val):
                row[f"{key}_SI"] = round((abs(plus_val) + abs(minus_val)) / 2.0, 3)
            else:
                row[f"{key}_SI"] = float("nan")

        rows.append(row)

    df = pd.DataFrame(rows).set_index("parameter")

    # Keep only SI columns for the main table
    si_cols = [c for c in df.columns if c.endswith("_SI")]
    table = df[si_cols].copy()
    table.columns = [c.replace("_SI", "") for c in si_cols]

    return SensitivityResult(table=table, baseline=baseline_metrics)
