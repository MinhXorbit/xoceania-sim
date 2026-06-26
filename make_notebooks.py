"""Generate the five xoceania-sim Jupyter notebooks using nbformat.

Run with: python make_notebooks.py
"""
import nbformat as nbf
from pathlib import Path

NB_DIR = Path("notebooks")
NB_DIR.mkdir(exist_ok=True)


def code(src: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(src.strip())


def md(src: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(src.strip())


def make_nb(cells, metadata: dict = None) -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    if metadata:
        nb.metadata.update(metadata)
    return nb


def save(nb, name: str):
    path = NB_DIR / name
    nbf.write(nb, str(path))
    print(f"  Saved {path}")


# ─────────────────────────────────────────────
# 01_quickstart.ipynb
# ─────────────────────────────────────────────
nb01 = make_nb([
    md("""# Xoceania Simulator — Quickstart

**Paper 1 companion notebook.**  
This notebook demonstrates the minimal workflow:
1. Load the default Vietnamese intensive shrimp pond config
2. Run a 48-hour simulation
3. Plot key water quality variables
"""),
    code("""# Standard imports
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
%matplotlib inline
plt.rcParams['figure.dpi'] = 120"""),
    code("""# Install / import xoceania_sim
# If not installed: pip install -e /path/to/xoceania_sim
from xoceania_sim import PondSimulator, SimConfig, load_config
from xoceania_sim import __version__
print(f"xoceania_sim v{__version__}")"""),
    md("""## 1. Configuration

`SimConfig` bundles `PondConfig`, `ShrimpConfig`, and `WeatherConfig`.
Default values represent a Vietnamese intensive *Penaeus vannamei* pond
in the Mekong Delta.
"""),
    code("""cfg = SimConfig()
print("Pond depth:", cfg.pond.depth_m, "m")
print("Stocking density:", cfg.shrimp.stocking_density_m2, "PL/m²")
print("Salinity:", cfg.pond.salinity_ppt, "ppt")
print("Aerators:", cfg.pond.n_aerators, "×", cfg.pond.aerator_power_kW, "kW")"""),
    md("## 2. Run the simulation"),
    code("""sim = PondSimulator(cfg)
result = sim.run(t_span=(0, 48))   # 48-hour run
df = result.df
print(result)
df.head()"""),
    md("## 3. Summary statistics"),
    code("""result.summary()"""),
    md("## 4. Time-series plots"),
    code("""fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
t = df.index

axes[0].plot(t, df['DO'], color='#1f77b4', lw=2)
axes[0].axhline(5, color='red', ls='--', lw=1, label='Stress threshold')
axes[0].set_ylabel('DO (mg/L)')
axes[0].set_ylim(0, 14)
axes[0].legend()

axes[1].plot(t, df['pH'], color='#ff7f0e', lw=2)
axes[1].set_ylabel('pH')
axes[1].set_ylim(6, 11)

axes[2].plot(t, df['T'], color='#d62728', lw=2)
axes[2].set_ylabel('Temperature (°C)')
axes[2].set_xlabel('Time (h from midnight)')
axes[2].set_ylim(25, 35)

for ax in axes:
    ax.set_xticks(range(0, 49, 6))
    ax.grid(True, alpha=0.3)

fig.suptitle('48-h Simulation — Vietnamese Intensive Shrimp Pond', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.show()"""),
    md("## 5. Nitrogen dynamics"),
    code("""fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
axes[0].plot(t, df['TAN'], label='TAN (mg N/L)', color='#2ca02c', lw=2)
axes[0].plot(t, df['NH3'], label='NH₃-N (mg N/L)', color='#9467bd', lw=2, ls='--')
axes[0].set_ylabel('Nitrogen (mg N/L)')
axes[0].legend()

axes[1].plot(t, df['A'], color='#17becf', lw=2)
axes[1].set_ylabel('Phytoplankton Chl-a (μg/L)')
axes[1].set_xlabel('Time (h)')

for ax in axes:
    ax.set_xticks(range(0, 49, 6))
    ax.grid(True, alpha=0.3)

fig.suptitle('Nitrogen and Phytoplankton Dynamics', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.show()"""),
])

save(nb01, "01_quickstart.ipynb")


# ─────────────────────────────────────────────
# 02_diurnal_exploration.ipynb
# ────────────────────────────────────────────
nb02 = make_nb([
    md("""# Diurnal Pattern Exploration

Explores how diurnal DO, pH, and temperature patterns respond to:
- Time of year (day of year)
- Cloud cover
- Wind speed

Reference: Szyper et al. (1992). *Aquacultural Engineering*, 11(2), 73-89.
"""),
    code("""import numpy as np
import matplotlib.pyplot as plt
%matplotlib inline
plt.rcParams['figure.dpi'] = 120
from xoceania_sim import PondSimulator, SimConfig"""),
    md("## 1. Effect of cloud cover on diurnal DO"),
    code("""import copy

fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
cloud_values = [0.0, 0.3, 0.6, 0.9]
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

for cloud, color in zip(cloud_values, colors):
    cfg = SimConfig()
    cfg.weather.cloud_cover = cloud
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 48))
    df = result.df
    t = df.index
    axes[0].plot(t, df['DO'], color=color, lw=2, label=f'cloud={cloud:.0%}')
    axes[1].plot(t, df['pH'], color=color, lw=2, label=f'cloud={cloud:.0%}')

axes[0].set_ylabel('DO (mg/L)')
axes[0].set_ylim(2, 16)
axes[0].axhline(5, color='gray', ls=':', lw=1)
axes[0].legend(fontsize=9)

axes[1].set_ylabel('pH')
axes[1].set_ylim(6.5, 11)
axes[1].set_xlabel('Time (h)')
axes[1].set_xticks(range(0, 49, 6))

fig.suptitle('Effect of Cloud Cover on Diurnal DO and pH', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.show()"""),
    md("## 2. Effect of day of year (seasonality)"),
    code("""fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
doy_values = [50, 100, 150, 200, 250, 300]
palette = plt.cm.plasma(np.linspace(0.1, 0.9, len(doy_values)))

for doy, color in zip(doy_values, palette):
    cfg = SimConfig()
    cfg.weather.day_of_year = doy
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 48))
    df = result.df
    t = df.index
    axes[0].plot(t, df['DO'], color=color, lw=1.5, label=f'DOY {doy}')
    axes[1].plot(t, df['T'], color=color, lw=1.5)

axes[0].set_ylabel('DO (mg/L)')
axes[0].legend(fontsize=8, ncol=2)
axes[1].set_ylabel('Temperature (°C)')
axes[1].set_xlabel('Time (h)')
axes[1].set_xticks(range(0, 49, 6))
fig.suptitle('Seasonal Effect on DO and Temperature (DOY)', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.show()"""),
    md("## 3. DO range analysis across cloud conditions"),
    code("""cloud_sweep = np.linspace(0.0, 0.95, 20)
do_max_vals, do_min_vals = [], []

for cloud in cloud_sweep:
    cfg = SimConfig()
    cfg.weather.cloud_cover = cloud
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 48))
    df = result.df
    # Second cycle only
    df2 = df[df.index >= 24]
    do_max_vals.append(df2['DO'].max())
    do_min_vals.append(df2['DO'].min())

fig, ax = plt.subplots(figsize=(8, 4))
ax.fill_between(cloud_sweep * 100, do_min_vals, do_max_vals, alpha=0.3, color='#1f77b4')
ax.plot(cloud_sweep * 100, do_max_vals, 'b-', lw=2, label='Daily max DO')
ax.plot(cloud_sweep * 100, do_min_vals, 'b--', lw=2, label='Daily min DO')
ax.axhline(5, color='red', ls=':', lw=1.5, label='5 mg/L stress threshold')
ax.set_xlabel('Cloud cover (%)')
ax.set_ylabel('DO (mg/L)')
ax.set_title('DO Range vs. Cloud Cover (48-h simulation, day 2)', fontsize=12, fontweight='bold')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()"""),
])

save(nb02, "02_diurnal_exploration.ipynb")


# ─────────────────────────────────────────────
# 03_ammonia_toxicity.ipynb
# ────────────────────────────────────────────
nb03 = make_nb([
    md("""# Ammonia Toxicity Analysis

Un-ionized ammonia (NH₃-N) is the primary toxic form for shrimp.
The fraction depends on pH and temperature.

**Acute toxicity threshold:** 0.3 mg NH₃-N/L (Wickins, 1976; Boyd & Tucker, 1998)
**Chronic toxicity threshold:** 0.1 mg NH₃-N/L

This notebook explores how TAN, pH, and temperature interact to
determine NH₃-N exposure risk in intensive shrimp ponds.
"""),
    code("""import numpy as np
import matplotlib.pyplot as plt
%matplotlib inline
plt.rcParams['figure.dpi'] = 120
from xoceania_sim import PondSimulator, SimConfig
from xoceania_sim.subsystems.nitrogen import nh3_fraction"""),
    md("## 1. NH₃ ionization fraction vs pH and temperature"),
    code("""pH_range = np.linspace(6.5, 10.0, 100)
temps = [25, 28, 30, 32, 35]
colors = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd']

fig, ax = plt.subplots(figsize=(9, 5))
for T, color in zip(temps, colors):
    fracs = [nh3_fraction(pH, T) for pH in pH_range]
    ax.plot(pH_range, fracs, color=color, lw=2, label=f'{T}°C')

ax.set_xlabel('pH', fontsize=12)
ax.set_ylabel('NH₃ ionization fraction (α)', fontsize=12)
ax.set_title('Un-ionized NH₃ Fraction vs pH and Temperature', fontsize=12, fontweight='bold')
ax.legend(title='Temperature', fontsize=10)
ax.set_xlim(6.5, 10.0)
ax.set_ylim(0, 1)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()"""),
    md("## 2. Simulate TAN and NH₃ over 48 hours at different stocking densities"),
    code("""fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
densities = [50, 100, 150, 200]
palette = ['#1f77b4', '#ff7f0e', '#d62728', '#9467bd']

for density, color in zip(densities, palette):
    cfg = SimConfig()
    cfg.shrimp.stocking_density_m2 = density
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 48))
    df = result.df
    t = df.index
    axes[0].plot(t, df['TAN'], color=color, lw=2, label=f'{density} PL/m²')
    axes[1].plot(t, df['NH3'], color=color, lw=2, label=f'{density} PL/m²')

axes[0].set_ylabel('TAN (mg N/L)')
axes[0].legend(fontsize=9, title='Stocking density')
axes[1].set_ylabel('NH₃-N (mg N/L)')
axes[1].axhline(0.1, color='orange', ls='--', lw=1.5, label='Chronic threshold 0.1')
axes[1].axhline(0.3, color='red', ls='--', lw=1.5, label='Acute threshold 0.3')
axes[1].legend(fontsize=9)
axes[1].set_xlabel('Time (h)')
axes[1].set_xticks(range(0, 49, 6))

for ax in axes:
    ax.grid(True, alpha=0.3)

fig.suptitle('TAN and NH₃-N Dynamics vs Stocking Density', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.show()"""),
    md("## 3. Risk map: NH₃ toxicity probability across pH × TAN space"),
    code("""pH_vals = np.linspace(7.0, 10.0, 50)
TAN_vals = np.linspace(0.0, 5.0, 50)
T_water = 29.0  # typical Mekong Delta temperature

pH_grid, TAN_grid = np.meshgrid(pH_vals, TAN_vals)
NH3_grid = np.vectorize(lambda ph, tan: nh3_fraction(ph, T_water) * tan)(pH_grid, TAN_grid)

fig, ax = plt.subplots(figsize=(8, 6))
CS = ax.contourf(pH_grid, TAN_grid, NH3_grid, levels=20, cmap='RdYlGn_r')
plt.colorbar(CS, ax=ax, label='NH₃-N (mg N/L)')
ax.contour(pH_grid, TAN_grid, NH3_grid, levels=[0.1, 0.3],
           colors=['orange', 'red'], linewidths=2)
ax.set_xlabel('pH', fontsize=12)
ax.set_ylabel('TAN (mg N/L)', fontsize=12)
ax.set_title(f'NH₃-N Toxicity Risk Map at T={T_water}°C\\n'
             f'Orange: chronic threshold (0.1), Red: acute threshold (0.3)',
             fontsize=11, fontweight='bold')
ax.grid(True, alpha=0.2, color='white')
plt.tight_layout()
plt.show()"""),
])

save(nb03, "03_ammonia_toxicity.ipynb")


# ─────────────────────────────────────────────
# 04_aeration_optimization.ipynb
# ─────────────────────────────────────────────
nb04 = make_nb([
    md("""# Aeration Strategy Optimization

Explores how different aeration strategies affect pond DO, with the goal
of maintaining DO ≥ 5 mg/L while minimizing energy cost.

Management scenarios:
1. Continuous (baseline)
2. Nighttime-only aeration (18:00–06:00)
3. Split schedule (high at night, low at day)
4. Number of aerators: 1, 2, 4

Reference: Boyd, C.E. & Tucker, C.S. (1998). *Pond Aquaculture Water 
Quality Management*. Kluwer Academic Publishers.
"""),
    code("""import numpy as np
import matplotlib.pyplot as plt
%matplotlib inline
plt.rcParams['figure.dpi'] = 120
from xoceania_sim import PondSimulator, SimConfig"""),
    md("## 1. Number of aerators"),
    code("""fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
aerator_counts = [1, 2, 4, 6]
colors = ['#9467bd', '#1f77b4', '#2ca02c', '#d62728']

for n, color in zip(aerator_counts, colors):
    cfg = SimConfig()
    cfg.pond.n_aerators = n
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 48))
    df = result.df
    t = df.index
    axes[0].plot(t, df['DO'], color=color, lw=2, label=f'{n} aerators')
    axes[1].plot(t, df['pH'], color=color, lw=2, label=f'{n} aerators')

axes[0].axhline(5, color='red', ls='--', lw=1, label='5 mg/L threshold')
axes[0].set_ylabel('DO (mg/L)')
axes[0].set_ylim(0, 18)
axes[0].legend(fontsize=9)

axes[1].set_ylabel('pH')
axes[1].set_xlabel('Time (h)')
axes[1].set_xticks(range(0, 49, 6))
axes[1].legend(fontsize=9)

for ax in axes:
    ax.grid(True, alpha=0.3)

fig.suptitle('Effect of Number of Aerators on DO and pH', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.show()"""),
    md("## 2. Aeration schedule: nighttime vs continuous"),
    code("""scenarios = {
    'Continuous (24 h)': None,  # default
    'Nighttime only (18–06)': {
        0.0: 1.0,   # 00:00 – full on
        6.0: 0.1,   # 06:00 – minimal
        18.0: 1.0,  # 18:00 – full on again
    },
    'Split (night high, day low)': {
        0.0: 1.0,
        6.0: 0.3,
        12.0: 0.5,
        18.0: 1.0,
    },
}

fig, ax = plt.subplots(figsize=(10, 4))
colors = ['#1f77b4', '#ff7f0e', '#2ca02c']

for (label, schedule), color in zip(scenarios.items(), colors):
    cfg = SimConfig()
    cfg.aeration_schedule = schedule
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(0, 48))
    df = result.df
    ax.plot(df.index, df['DO'], color=color, lw=2, label=label)

ax.axhline(5, color='red', ls=':', lw=1.5, label='5 mg/L threshold')
ax.set_xlabel('Time (h)')
ax.set_ylabel('DO (mg/L)')
ax.set_ylim(0, 16)
ax.set_xticks(range(0, 49, 6))
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
ax.set_title('Aeration Schedule Comparison — DO over 48 h', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.show()"""),
    md("## 3. Energy vs. minimum DO trade-off"),
    code("""n_aerators_range = range(1, 9)
do_min_vals = []
energy_kwh_day = []  # 2 kW per aerator × 24 h

for n in n_aerators_range:
    cfg = SimConfig()
    cfg.pond.n_aerators = n
    sim = PondSimulator(cfg)
    result = sim.run(t_span=(24, 72))  # start from equilibrated day 2
    df = result.df
    do_min_vals.append(df['DO'].min())
    energy_kwh_day.append(n * cfg.pond.aerator_power_kW * 24)

fig, ax1 = plt.subplots(figsize=(8, 4))
ax2 = ax1.twinx()

ax1.plot(list(n_aerators_range), do_min_vals, 'b-o', lw=2, label='Min DO (mg/L)')
ax1.axhline(5, color='blue', ls='--', lw=1, alpha=0.5)
ax1.set_xlabel('Number of aerators')
ax1.set_ylabel('Minimum DO (mg/L)', color='blue')
ax1.set_ylim(0, 14)

ax2.plot(list(n_aerators_range), energy_kwh_day, 'r-s', lw=2, label='Energy (kWh/day)')
ax2.set_ylabel('Energy consumption (kWh/day)', color='red')

ax1.set_title('Aerator Count vs. Minimum DO and Energy Cost', fontsize=12, fontweight='bold')
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9)
ax1.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()"""),
])

save(nb04, "04_aeration_optimization.ipynb")


# ─────────────────────────────────────────────
# 05_gym_environment_demo.ipynb
# ─────────────────────────────────────────────
nb05 = make_nb([
    md("""# Gym Environment Demo — XoceaniaPondEnv

`XoceaniaPondEnv` wraps `PondSimulator` as a [Gymnasium](https://gymnasium.farama.org/) 
environment for reinforcement learning.

**State space (10-dim):** T, DO, pH, TAN, NH3, Chl-a, W, B, time_of_day, DO_sat  
**Action space (3-dim, continuous [0,1]):** aeration_fraction, feed_fraction, water_exchange_fraction  
**Reward:** shaped to maximize shrimp growth while penalizing DO stress, NH₃ toxicity, and energy cost.

This notebook demonstrates:
1. Environment creation and reset
2. Random policy rollout
3. Simple rule-based policy (aerate at night, feed at dawn)
"""),
    code("""import numpy as np
import matplotlib.pyplot as plt
%matplotlib inline
plt.rcParams['figure.dpi'] = 120
from xoceania_sim import XoceaniaPondEnv, SimConfig"""),
    md("## 1. Create and inspect the environment"),
    code("""env = XoceaniaPondEnv()
print("Observation space:", env.observation_space)
print("Action space:", env.action_space)
print("Obs shape:", env.observation_space.shape)
print("Action bounds low:", env.action_space.low)
print("Action bounds high:", env.action_space.high)"""),
    md("## 2. Reset and step"),
    code("""obs, info = env.reset(seed=42)
print("Initial observation:", obs)
print("Info:", info)

# Take one step with random action
action = env.action_space.sample()
print("\\nRandom action:", action)
obs, reward, terminated, truncated, info = env.step(action)
print("Next observation:", obs)
print("Reward:", reward)
print("Done:", terminated or truncated)"""),
    md("## 3. Random policy rollout"),
    code("""obs, _ = env.reset(seed=0)
obs_history = [obs]
reward_history = []
info_history = []
done = False

np.random.seed(42)
while not done:
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    obs_history.append(obs)
    reward_history.append(reward)
    info_history.append(info)
    done = terminated or truncated

obs_arr = np.array(obs_history)
print(f"Episode length: {len(reward_history)} steps")
print(f"Total reward: {sum(reward_history):.2f}")
print(f"Mean reward per step: {np.mean(reward_history):.4f}")"""),
    md("## 4. Plot random policy trajectory"),
    code("""# Observation indices
OBS_T, OBS_DO, OBS_PH, OBS_TAN, OBS_NH3, OBS_A, OBS_W, OBS_B, OBS_TOD, OBS_DOSAT = range(10)
t_steps = np.arange(len(obs_arr))

fig, axes = plt.subplots(3, 2, figsize=(13, 9))

axes[0,0].plot(t_steps, obs_arr[:, OBS_DO], color='#1f77b4', lw=1.5)
axes[0,0].axhline(5, color='red', ls='--', lw=1)
axes[0,0].set_ylabel('DO (mg/L)')
axes[0,0].set_title('Dissolved Oxygen')

axes[0,1].plot(t_steps, obs_arr[:, OBS_PH], color='#ff7f0e', lw=1.5)
axes[0,1].set_ylabel('pH')
axes[0,1].set_title('pH')

axes[1,0].plot(t_steps, obs_arr[:, OBS_T], color='#d62728', lw=1.5)
axes[1,0].set_ylabel('T (°C)')
axes[1,0].set_title('Temperature')

axes[1,1].plot(t_steps, obs_arr[:, OBS_TAN], color='#2ca02c', lw=1.5, label='TAN')
axes[1,1].plot(t_steps, obs_arr[:, OBS_NH3], color='#9467bd', lw=1.5, ls='--', label='NH₃')
axes[1,1].set_ylabel('N (mg/L)')
axes[1,1].set_title('Nitrogen')
axes[1,1].legend(fontsize=9)

axes[2,0].plot(t_steps, obs_arr[:, OBS_W], color='#8c564b', lw=1.5)
axes[2,0].set_ylabel('Weight (g)')
axes[2,0].set_title('Shrimp Individual Weight')
axes[2,0].set_xlabel('Step (h)')

axes[2,1].plot(t_steps[1:], reward_history, color='#17becf', lw=1)
axes[2,1].set_ylabel('Reward')
axes[2,1].set_title('Step Reward (random policy)')
axes[2,1].set_xlabel('Step (h)')

for ax in axes.flat:
    ax.grid(True, alpha=0.3)

fig.suptitle('Random Policy Rollout — XoceaniaPondEnv', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.show()"""),
    md("## 5. Rule-based policy: aerate at night, no aeration during peak sun"),
    code("""def rule_based_action(obs):
    \"\"\"Heuristic: full aeration at night, reduced by day; feed twice daily.\"\"\"
    time_of_day = obs[OBS_TOD] * 24.0   # rescaled to 0-24h
    do = obs[OBS_DO]
    
    # Aeration: full at night or if DO low
    if time_of_day < 6 or time_of_day > 18 or do < 6:
        aer_frac = 1.0
    else:
        aer_frac = 0.5
    
    # Feed at dawn (06:00-08:00) and dusk (17:00-19:00)
    if (6 <= time_of_day <= 8) or (17 <= time_of_day <= 19):
        feed_frac = 1.0
    else:
        feed_frac = 0.0
    
    # No water exchange
    exchange_frac = 0.0
    
    return np.array([aer_frac, feed_frac, exchange_frac], dtype=np.float32)

obs, _ = env.reset(seed=0)
obs_rb = [obs]
reward_rb = []
done = False

while not done:
    action = rule_based_action(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    obs_rb.append(obs)
    reward_rb.append(reward)
    done = terminated or truncated

obs_rb_arr = np.array(obs_rb)
print(f"Rule-based episode length: {len(reward_rb)} steps")
print(f"Total reward: {sum(reward_rb):.2f} vs random: {sum(reward_history):.2f}")
print(f"Improvement: {(sum(reward_rb) - sum(reward_history)) / abs(sum(reward_history)) * 100:.1f}%")"""),
    code("""fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
t_rb = np.arange(len(obs_rb_arr))

axes[0].plot(t_rb, obs_rb_arr[:, OBS_DO], label='Rule-based', color='#2ca02c', lw=2)
axes[0].plot(t_steps, obs_arr[:, OBS_DO], label='Random', color='#1f77b4', lw=1, alpha=0.6, ls='--')
axes[0].axhline(5, color='red', ls=':', lw=1.5, label='5 mg/L stress threshold')
axes[0].set_ylabel('DO (mg/L)')
axes[0].legend(fontsize=9)
axes[0].set_title('DO: Rule-based vs Random Policy', fontsize=12, fontweight='bold')

axes[1].plot(t_rb[1:], np.cumsum(reward_rb), label='Rule-based', color='#2ca02c', lw=2)
axes[1].plot(t_steps[1:], np.cumsum(reward_history), label='Random', color='#1f77b4', lw=1, alpha=0.6, ls='--')
axes[1].set_ylabel('Cumulative Reward')
axes[1].set_xlabel('Step (h)')
axes[1].legend(fontsize=9)
axes[1].set_title('Cumulative Reward Comparison', fontsize=12, fontweight='bold')

for ax in axes:
    ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()"""),
    code("""env.close()
print("Environment closed.")"""),
])

save(nb05, "05_gym_environment_demo.ipynb")

print("\nAll 5 notebooks generated successfully!")
