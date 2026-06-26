"""Environmental forcing subpackage.

Provides solar irradiance, weather generation, and the unified EnvironmentalForcing
interface used by the coupled ODE system.
"""

from xoceania_sim.forcing.solar import (
    bird_hulstrom_irradiance,
    clear_sky_irradiance,
    par_underwater,
)
from xoceania_sim.forcing.weather import (
    SyntheticWeather,
    CSVWeather,
)
from xoceania_sim.forcing.forcing import (
    ForcingState,
    EnvironmentalForcing,
    create_forcing,
)

__all__ = [
    "bird_hulstrom_irradiance",
    "clear_sky_irradiance",
    "par_underwater",
    "SyntheticWeather",
    "CSVWeather",
    "ForcingState",
    "EnvironmentalForcing",
    "create_forcing",
]
