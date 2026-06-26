"""Publication-quality figure generation for xoceania-sim.

All figures are saved at 300 dpi (PNG) and as vector (SVG) for journal
submission. Style follows matplotlib's default with minor customization
for clarity and readability.

References:
    Wilkinson, L. (2005). The Grammar of Graphics (2nd ed.). Springer.
    Rougier, N.P. et al. (2014). Ten simple rules for better figures.
        PLOS Comput. Biol., 10(9), e1003833.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless rendering
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import pandas as pd

from xoceania_sim import PondSimulator, SimConfig
from xoceania_sim.validation.diurnal_validation import (
    run_diurnal_validation,
    get_field_reference_data,
    DiurnalValidationResult,
)
from xoceania_sim.validation.boyd_dobudget import run_boyd_budget, BoydBudgetResult
from xoceania_sim.validation.sensitivity import run_sensitivity_analysis, SensitivityResult


# Publication style constants
_DPI = 300
_FIGSIZE_DOUBLE = (10, 8)
_FIGSIZE_SINGLE = (7, 5)
_COLORS = {
    "DO": "#1f77b4",
    "pH": "#ff7f0e",
    "T": "#d62728",
    "TAN": "#2ca02c",
    "field": "#555555",
    "sim": "#e377c2",
}


def save_figure(
    fig: plt.Figure,
    stem: str,
    out_dir: Path | str,
    dpi: int = _DPI,
) -> tuple[Path, Path]:
    """Save a matplotlib figure as both PNG and SVG.

    Args:
        fig: The figure to save.
        stem: Filename stem (no extension).
        out_dir: Output directory path.
        dpi: Resolution for PNG output (default 300 dpi).

    Returns:
        Tuple of (png_path, svg_path).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{stem}.png"
    svg_path = out_dir / f"{stem}.svg"
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    return png_path, svg_path


def plot_diurnal_validation(
    val_result: Optional[DiurnalValidationResult] = None,
    out_dir: Optional[Path | str] = None,
) -> plt.Figure:
    """Plot simulated vs field diurnal cycles for DO, pH, and temperature.

    Creates a 3-panel figure showing 48-hour simulation output overlaid on
    digitized field reference data from Vietnamese intensive shrimp ponds.

    Args:
        val_result: Pre-computed DiurnalValidationResult. If None, runs validation.
        out_dir: If provided, saves PNG and SVG to this directory.

    Returns:
        matplotlib Figure object.
    """
    if val_result is None:
        val_result = run_diurnal_validation()

    field = get_field_reference_data()
    df = val_result.sim_df

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    fig.suptitle(
        "Simulated vs. Field Diurnal Cycles — Vietnamese Intensive Shrimp Pond",
        fontsize=13, fontweight="bold", y=1.01,
    )

    t_full = df.index.values.astype(float)

    # Panel 1: DO
    ax = axes[0]
    ax.plot(t_full, df["DO"].values, color=_COLORS["DO"], lw=2, label="Simulated")
    fd = field["DO"]
    ax.errorbar(
        fd["hours"], fd["mean"], yerr=fd["sd"],
        fmt="o", color=_COLORS["field"], capsize=4, label="Field (Boyd 1990; Tran 2019)",
        zorder=5,
    )
    # Repeat field points at +24 for second cycle
    ax.errorbar(
        fd["hours"] + 24, fd["mean"], yerr=fd["sd"],
        fmt="o", color=_COLORS["field"], capsize=4, zorder=5, alpha=0.5,
    )
    ax.set_ylabel("DO (mg/L)", fontsize=11)
    ax.set_ylim(0, 16)
    ax.axhline(5.0, color="gray", ls="--", lw=0.8, label="Stress threshold (5 mg/L)")
    ax.legend(fontsize=9, loc="upper right")
    ax.text(0.02, 0.92, f"RMSE = {val_result.rmse_do:.2f} mg/L",
            transform=ax.transAxes, fontsize=9, color="#333333")
    _add_nightshade(ax, t_full)

    # Panel 2: pH
    ax = axes[1]
    ax.plot(t_full, df["pH"].values, color=_COLORS["pH"], lw=2, label="Simulated")
    fd = field["pH"]
    ax.errorbar(
        fd["hours"], fd["mean"], yerr=fd["sd"],
        fmt="s", color=_COLORS["field"], capsize=4, label="Field (Boyd 1990)",
        zorder=5,
    )
    ax.errorbar(
        fd["hours"] + 24, fd["mean"], yerr=fd["sd"],
        fmt="s", color=_COLORS["field"], capsize=4, zorder=5, alpha=0.5,
    )
    ax.set_ylabel("pH", fontsize=11)
    ax.set_ylim(6.5, 10.5)
    ax.legend(fontsize=9, loc="upper right")
    ax.text(0.02, 0.92, f"RMSE = {val_result.rmse_ph:.2f}",
            transform=ax.transAxes, fontsize=9, color="#333333")
    _add_nightshade(ax, t_full)

    # Panel 3: Temperature
    ax = axes[2]
    ax.plot(t_full, df["T"].values, color=_COLORS["T"], lw=2, label="Simulated")
    fd = field["T"]
    ax.errorbar(
        fd["hours"], fd["mean"], yerr=fd["sd"],
        fmt="^", color=_COLORS["field"], capsize=4, label="Field (Boyd 1990)",
        zorder=5,
    )
    ax.errorbar(
        fd["hours"] + 24, fd["mean"], yerr=fd["sd"],
        fmt="^", color=_COLORS["field"], capsize=4, zorder=5, alpha=0.5,
    )
    ax.set_ylabel("Temperature (°C)", fontsize=11)
    ax.set_ylim(24, 36)
    ax.set_xlabel("Time (h from midnight)", fontsize=11)
    ax.set_xticks(np.arange(0, 49, 6))
    ax.legend(fontsize=9, loc="upper right")
    ax.text(0.02, 0.92, f"RMSE = {val_result.rmse_t:.2f} °C",
            transform=ax.transAxes, fontsize=9, color="#333333")
    _add_nightshade(ax, t_full)

    fig.tight_layout()

    if out_dir is not None:
        save_figure(fig, "fig_validation_diurnal", out_dir)

    return fig


def plot_do_budget(
    budget_result: Optional[BoydBudgetResult] = None,
    out_dir: Optional[Path | str] = None,
) -> plt.Figure:
    """Plot nighttime DO budget as a grouped bar chart vs Boyd (1990) targets.

    Args:
        budget_result: Pre-computed BoydBudgetResult. If None, runs validation.
        out_dir: If provided, saves PNG and SVG to this directory.

    Returns:
        matplotlib Figure object.
    """
    if budget_result is None:
        budget_result = run_boyd_budget()

    labels = ["Plankton\nrespiration", "Sediment\noxygen demand", "Fish/shrimp\nrespiration"]
    sim_vals = [
        budget_result.plankton_fraction,
        budget_result.sediment_fraction,
        budget_result.fish_fraction,
    ]
    target_vals = [
        budget_result.target["plankton"],
        budget_result.target["sediment"],
        budget_result.target["fish"],
    ]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax.bar(x - width / 2, sim_vals, width, label="Simulated (xoceania-sim)",
                   color="#4878cf", edgecolor="white", lw=1.2)
    bars2 = ax.bar(x + width / 2, target_vals, width, label="Boyd (1990) field data",
                   color="#6acc65", edgecolor="white", lw=1.2, alpha=0.8)

    # Add tolerance bands
    tol = 0.15
    for i, (tgt, bar) in enumerate(zip(target_vals, bars2)):
        ax.errorbar(x[i] + width / 2, tgt, yerr=tol * tgt,
                    fmt="none", color="#333333", capsize=6, lw=1.5)

    ax.set_ylabel("Fraction of nighttime DO consumption", fontsize=11)
    ax.set_title("Nighttime DO Budget Validation vs. Boyd (1990)", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 1.0)
    ax.legend(fontsize=10)

    # Pass/fail annotations
    for i, (key, bar) in enumerate(zip(["plankton", "sediment", "fish"], bars1)):
        passed = budget_result.passes[key]
        marker = "✓" if passed else "✗"
        color = "#1a9850" if passed else "#d73027"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                marker, ha="center", va="bottom", color=color, fontsize=14, fontweight="bold")

    ax.text(0.98, 0.97,
            "Error bars = ±15% tolerance\nCheck = within tolerance",
            transform=ax.transAxes, fontsize=8, va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", alpha=0.8))

    fig.tight_layout()

    if out_dir is not None:
        save_figure(fig, "fig_do_budget", out_dir)

    return fig


def plot_sensitivity(
    sens_result: Optional[SensitivityResult] = None,
    out_dir: Optional[Path | str] = None,
) -> plt.Figure:
    """Plot OAT sensitivity analysis as a heatmap.

    Args:
        sens_result: Pre-computed SensitivityResult. If None, runs analysis.
        out_dir: If provided, saves PNG and SVG to this directory.

    Returns:
        matplotlib Figure object.
    """
    if sens_result is None:
        sens_result = run_sensitivity_analysis()

    table = sens_result.table.copy()

    # Rename columns for display
    col_labels = {
        "DO_mean": "DO\n(mean)",
        "DO_min": "DO\n(min)",
        "pH_mean": "pH\n(mean)",
        "TAN_mean": "TAN\n(mean)",
        "T_mean": "T\n(mean)",
    }
    table.columns = [col_labels.get(c, c) for c in table.columns]

    fig, ax = plt.subplots(figsize=(9, 6))
    data = table.values.astype(float)

    # Use symmetric colormap centered at 0
    vmax = np.nanpercentile(np.abs(data), 95)
    im = ax.imshow(data, cmap="RdBu_r", aspect="auto", vmin=-vmax, vmax=vmax)

    ax.set_xticks(np.arange(len(table.columns)))
    ax.set_xticklabels(table.columns, fontsize=10)
    ax.set_yticks(np.arange(len(table.index)))
    ax.set_yticklabels(table.index, fontsize=10)

    # Annotate cells
    for i in range(len(table.index)):
        for j in range(len(table.columns)):
            val = data[i, j]
            if np.isfinite(val):
                text = ax.text(j, i, f"{val:.0f}",
                               ha="center", va="center", fontsize=8,
                               color="white" if abs(val) > vmax * 0.6 else "black")

    plt.colorbar(im, ax=ax, label="Sensitivity index (% output change / % parameter change)", shrink=0.8)
    ax.set_title("One-at-a-Time Sensitivity Analysis (±20% perturbation, 48 h)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel("Output metric", fontsize=11)
    ax.set_ylabel("Parameter", fontsize=11)

    fig.tight_layout()

    if out_dir is not None:
        save_figure(fig, "fig_sensitivity", out_dir)

    return fig


def plot_scenarios(
    out_dir: Optional[Path | str] = None,
) -> plt.Figure:
    """Plot scenario comparison: baseline vs high-aeration vs low-stocking.

    Compares three management scenarios over 48 hours:
    - Baseline: standard Vietnamese intensive pond
    - High aeration: 4 × 2 kW aerators (doubled)
    - Low stocking: 50 PL/m² (half density)

    Args:
        out_dir: If provided, saves PNG and SVG to this directory.

    Returns:
        matplotlib Figure object.
    """
    scenarios = {}

    # Baseline
    cfg_base = SimConfig()
    scenarios["Baseline (100 PL/m², 2 aerators)"] = cfg_base

    # High aeration
    cfg_hi_aer = copy.deepcopy(cfg_base)
    cfg_hi_aer.pond.n_aerators = 4
    scenarios["High aeration (4 aerators)"] = cfg_hi_aer

    # Low stocking
    cfg_lo_stock = copy.deepcopy(cfg_base)
    cfg_lo_stock.shrimp.stocking_density_m2 = 50.0
    scenarios["Low stocking (50 PL/m²)"] = cfg_lo_stock

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    ls_styles = ["-", "--", "-."]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    plot_vars = [
        ("DO", "DO (mg/L)", (0, 16)),
        ("pH", "pH", (6.5, 10.5)),
        ("T", "Temperature (°C)", (25, 35)),
        ("TAN", "TAN (mg N/L)", (0, 2.0)),
    ]

    for (label, cfg), color, ls in zip(scenarios.items(), colors, ls_styles):
        sim = PondSimulator(cfg)
        result = sim.run(t_span=(0, 48))
        df = result.df
        t = df.index.values

        for ax, (col, ylabel, ylim) in zip(axes, plot_vars):
            ax.plot(t, df[col].values, color=color, ls=ls, lw=2, label=label)

    for ax, (col, ylabel, ylim) in zip(axes, plot_vars):
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xlabel("Time (h)", fontsize=11)
        ax.set_xlim(0, 48)
        ax.set_ylim(*ylim)
        ax.set_xticks(np.arange(0, 49, 12))
        _add_nightshade(ax, np.linspace(0, 48, 200))
        if col == "DO":
            ax.axhline(5.0, color="gray", ls=":", lw=0.8)

    axes[0].legend(fontsize=9, loc="upper right")
    fig.suptitle(
        "Scenario Comparison: Management Interventions (48 h)",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()

    if out_dir is not None:
        save_figure(fig, "fig_scenarios", out_dir)

    return fig


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _add_nightshade(ax: plt.Axes, t_arr: np.ndarray) -> None:
    """Shade nighttime hours (18:00–06:00 next day) on an axis.

    Args:
        ax: Axes to shade.
        t_arr: Time array to determine x-axis range.
    """
    t_max = float(t_arr.max())
    t_start = 0.0
    while t_start <= t_max:
        # Night: 0-6h and 18-24h in each day
        for night_start, night_end in [(0, 6), (18, 24)]:
            shade_start = t_start + night_start
            shade_end = t_start + night_end
            if shade_start < t_max:
                ax.axvspan(
                    shade_start, min(shade_end, t_max),
                    alpha=0.08, color="navy", lw=0,
                )
        t_start += 24.0
