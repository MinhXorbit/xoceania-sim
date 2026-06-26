"""Subsystem ODE modules for xoceania-sim.

Each module exports a pure function ``d<state>_dt`` and a ``<Subsystem>Params`` dataclass.
Temperature dependence uses Arrhenius θ^(T-20) form throughout.
"""

from xoceania_sim.subsystems.temperature import dT_dt, TemperatureParams
from xoceania_sim.subsystems.dissolved_oxygen import dDO_dt, DOParams, do_saturation
from xoceania_sim.subsystems.ph_carbon import dCT_dt, solve_pH, CarbonParams
from xoceania_sim.subsystems.nitrogen import dTAN_dt, NitrogenParams, nh3_fraction
from xoceania_sim.subsystems.phytoplankton import dA_dt, PhytoplanktonParams
from xoceania_sim.subsystems.shrimp import ShrimpState, ShrimpParams, update_shrimp

__all__ = [
    "dT_dt", "TemperatureParams",
    "dDO_dt", "DOParams", "do_saturation",
    "dCT_dt", "solve_pH", "CarbonParams",
    "dTAN_dt", "NitrogenParams", "nh3_fraction",
    "dA_dt", "PhytoplanktonParams",
    "ShrimpState", "ShrimpParams", "update_shrimp",
]
