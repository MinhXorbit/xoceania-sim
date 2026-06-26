"""Validation scripts for xoceania-sim.

Provides three validation modules:
- diurnal_validation: Compare simulated diurnal DO/pH/T against published
  field data from Vietnamese intensive shrimp ponds.
- boyd_dobudget: Reproduce Boyd (1990) nighttime DO budget fractions.
- sensitivity: One-at-a-time sensitivity analysis across key parameters.
"""

from xoceania_sim.validation.diurnal_validation import run_diurnal_validation
from xoceania_sim.validation.boyd_dobudget import run_boyd_budget
from xoceania_sim.validation.sensitivity import run_sensitivity_analysis

__all__ = ["run_diurnal_validation", "run_boyd_budget", "run_sensitivity_analysis"]
