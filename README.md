# xoceania-sim

**Xoceania** is a coupled ODE simulator for aquaculture pond water quality, parameterized for
Vietnamese intensive *Penaeus vannamei* (whiteleg shrimp) ponds in the Mekong Delta.
This is **Paper 1** of the Xoceania research series — the process-based foundation that underlies
an RL training environment in subsequent work.

## Features

- Coupled ODE subsystems: Temperature ↔ DO ↔ Phytoplankton ↔ pH/C_T ↔ NH₃/TAN
- Bird-Hulstrom (1981) solar model with cloud-cover correction
- Arrhenius temperature corrections on all rate constants
- Newton-Raphson carbonate equilibrium solver (Millero 2010)
- Penaeus vannamei shrimp growth, respiration, and excretion module
- `gymnasium`-compatible environment for reinforcement learning
- LSODA stiff ODE integrator via `scipy.integrate.solve_ivp`
- Event detection: DO crash, pH exceedance, supersaturation
- Publication figures (300 dpi PNG + SVG)

## Installation

```bash
pip install xoceania-sim
```

Or from source (editable):

```bash
git clone https://github.com/xoceania/xoceania-sim
cd xoceania-sim
pip install -e ".[dev]"
```

## Quickstart

```python
from xoceania_sim import PondSimulator, load_config

# Load Mekong Delta vannamei configuration
cfg = load_config("configs/vannamei_mekong.yaml")

# Run 7-day simulation
sim = PondSimulator(cfg)
result = sim.run(t_span=(0, 7 * 24), method="LSODA")

# result is a pandas DataFrame
print(result[["DO", "pH", "T", "TAN", "NH3", "A"]].describe())

# Plot
import matplotlib.pyplot as plt
fig, axes = plt.subplots(3, 1, figsize=(10, 8))
result["DO"].plot(ax=axes[0], ylabel="DO (mg/L)")
result["pH"].plot(ax=axes[1], ylabel="pH")
result["T"].plot(ax=axes[2], ylabel="Temperature (°C)")
plt.tight_layout()
plt.savefig("quickstart_output.png", dpi=150)
```

### Gymnasium Environment

```python
from xoceania_sim import XoceaniaPondEnv
import numpy as np

env = XoceaniaPondEnv()
obs, info = env.reset()
for _ in range(100):
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        obs, info = env.reset()
```

## Configuration

Pre-built configs:
- `configs/vannamei_mekong.yaml` — Vietnamese intensive shrimp pond
- `configs/catfish_alabama.yaml` — Alabama catfish pond (Boyd 1979 validation)

## Citation

If you use `xoceania-sim` in your research, please cite:

```bibtex
@article{nguyen2026xoceania,
  title     = {Xoceania: An open-source coupled {ODE} simulator for aquaculture pond
               water quality with reinforcement learning support},
  author    = {Nguyen, Minh},
  journal   = {Environmental Modelling \& Software},
  year      = {2026},
  volume    = {},
  pages     = {},
  doi       = {10.xxxx/xxxxxxx},
  url       = {https://github.com/xoceania/xoceania-sim}
}
```

## Manuscript

See [`manuscript/paper1_simulator.md`](manuscript/paper1_simulator.md) for the full model description.

## License

MIT License © 2026 Minh Nguyen
