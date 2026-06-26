"""Visualization utilities for xoceania-sim.

Generates publication-quality figures (300 dpi PNG + SVG) for:
- Diurnal validation (DO, pH, T) against field data
- Boyd (1990) nighttime DO budget pie chart
- OAT sensitivity heatmap
- Scenario comparison (management interventions)
"""

from xoceania_sim.viz.figures import (
    plot_diurnal_validation,
    plot_do_budget,
    plot_sensitivity,
    plot_scenarios,
    save_figure,
)

__all__ = [
    "plot_diurnal_validation",
    "plot_do_budget",
    "plot_sensitivity",
    "plot_scenarios",
    "save_figure",
]
