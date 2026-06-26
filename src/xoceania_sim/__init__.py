"""xoceania-sim: Coupled ODE simulator for aquaculture pond water quality.

Paper 1 of the Xoceania research series.
Parameterized for Vietnamese intensive Penaeus vannamei ponds, Mekong Delta.

Top-level API:
    PondSimulator: Coupled ODE integrator for pond water quality.
    XoceaniaPondEnv: Gymnasium-compatible RL environment.
    load_config: Load SimConfig from a YAML file.
    __version__: Package version string.

Example:
    >>> from xoceania_sim import PondSimulator, load_config
    >>> cfg = load_config("configs/vannamei_mekong.yaml")
    >>> sim = PondSimulator(cfg)
    >>> result = sim.run(t_span=(0, 48))
    >>> print(result.df[["DO", "pH", "T"]].describe())
"""

from xoceania_sim.simulator import PondSimulator, SimulationResult
from xoceania_sim.environments.pond_env import XoceaniaPondEnv
from xoceania_sim.config import (
    load_config,
    SimConfig,
    PondConfig,
    ShrimpConfig,
    WeatherConfig,
)

__version__ = "0.1.0"
__author__ = "Minh Nguyen"
__license__ = "MIT"

__all__ = [
    "PondSimulator",
    "SimulationResult",
    "XoceaniaPondEnv",
    "load_config",
    "SimConfig",
    "PondConfig",
    "ShrimpConfig",
    "WeatherConfig",
    "__version__",
]
