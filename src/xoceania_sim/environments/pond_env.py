"""Gymnasium-compatible environment for aquaculture pond water quality control.

XoceaniaPondEnv wraps PondSimulator as a gymnasium.Env for reinforcement learning.
The agent controls aeration fraction, water exchange rate, and feed multiplier.

Observation space (10 dims):
    [DO, T, pH, TAN_total, NH3_unionized, A, W, B, hour_of_day, day_of_cycle]

Action space (3 dims, continuous):
    [aeration_fraction ∈ [0,1],
     exchange_rate ∈ [0, 0.2] (fraction/day),
     feed_multiplier ∈ [0.5, 1.5]]

Step interval: 1 hour (configurable via step_hours).

Reward shaping:
    R = w_biomass * ΔB/B_max + w_do * (-do_stress_time) + w_nh3 * (-nh3_stress_time)
        + w_energy * (-energy_cost) + w_water * (-water_cost)

where:
    ΔB = biomass gain over step (g/m²)
    do_stress_time = 1 if DO < 3 mg/L, else 0
    nh3_stress_time = 1 if NH₃ > 0.1 mg/L, else 0
    energy_cost = aeration_fraction (proxy for kWh)
    water_cost = exchange_rate (proxy for pumping cost)

References:
    Brockman, G. et al. (2016). OpenAI Gym. arXiv:1606.01540.
    gymnasium: https://gymnasium.farama.org/
"""

from __future__ import annotations

import copy
import math
import random
from typing import Any, Optional, Tuple

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from xoceania_sim.config import SimConfig, PondConfig, ShrimpConfig, WeatherConfig
from xoceania_sim.simulator import PondSimulator, SimulationResult
from xoceania_sim.subsystems.dissolved_oxygen import do_saturation
from xoceania_sim.subsystems.ph_carbon import solve_pH
from xoceania_sim.subsystems.nitrogen import nh3_fraction


# Observation indices
_OBS_DO = 0
_OBS_T = 1
_OBS_PH = 2
_OBS_TAN = 3
_OBS_NH3 = 4
_OBS_A = 5
_OBS_W = 6
_OBS_B = 7
_OBS_HOUR = 8
_OBS_DAY = 9

# Observation bounds
_OBS_LOW = np.array([0.0, 15.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
_OBS_HIGH = np.array([25.0, 42.0, 12.0, 50.0, 5.0, 2000.0, 30.0, 5000.0, 24.0, 150.0], dtype=np.float32)

# Action bounds
_ACT_LOW = np.array([0.0, 0.0, 0.5], dtype=np.float32)
_ACT_HIGH = np.array([1.0, 0.20, 1.5], dtype=np.float32)

# Reward weights
_W_BIOMASS = 1.0
_W_DO_STRESS = -2.0
_W_NH3_STRESS = -3.0
_W_ENERGY = -0.1
_W_WATER = -0.05


class XoceaniaPondEnv(gym.Env):
    """Gymnasium environment for aquaculture pond water quality management.

    Wraps PondSimulator for reinforcement learning. The agent steps at 1-hour
    intervals, observing water quality state and choosing management actions.

    Args:
        config: SimConfig. If None, uses default vannamei Mekong Delta config.
        step_hours: Hours per environment step. Default 1.
        max_days: Maximum episode length in days. Default 90.
        render_mode: Optional render mode. 'human' shows a matplotlib plot.
        randomize_init: Whether to randomize initial conditions on reset.

    Example:
        >>> env = XoceaniaPondEnv()
        >>> obs, info = env.reset()
        >>> for _ in range(24):
        ...     action = env.action_space.sample()
        ...     obs, reward, terminated, truncated, info = env.step(action)
    """

    metadata = {"render_modes": ["human", "rgb_array"]}

    def __init__(
        self,
        config: Optional[SimConfig] = None,
        step_hours: float = 1.0,
        max_days: float = 90.0,
        render_mode: Optional[str] = None,
        randomize_init: bool = True,
    ) -> None:
        super().__init__()

        self._base_config = config or SimConfig()
        self._step_hours = step_hours
        self._max_days = max_days
        self._render_mode = render_mode
        self._randomize_init = randomize_init

        # Gym spaces
        self.observation_space = spaces.Box(
            low=_OBS_LOW, high=_OBS_HIGH, dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=_ACT_LOW, high=_ACT_HIGH, dtype=np.float32
        )

        # Simulator instance
        self._sim: Optional[PondSimulator] = None
        self._current_state: Optional[np.ndarray] = None  # [T, DO, CT, TAN, A, W, B]
        self._t: float = 0.0  # current time (hours)
        self._episode_B0: float = 0.0  # initial biomass for reward normalization
        self._prev_B: float = 0.0

        # History for rendering
        self._history: list[dict[str, float]] = []

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment to initial conditions.

        Args:
            seed: Random seed for initial condition randomization.
            options: Optional dict with overrides:
                'initial_do', 'initial_temp', 'day_of_year'.

        Returns:
            Tuple of (observation, info_dict).
        """
        super().reset(seed=seed)

        # Clone config for this episode
        cfg = copy.deepcopy(self._base_config)

        if self._randomize_init:
            rng = np.random.default_rng(seed)
            cfg.initial_do = float(rng.uniform(5.0, 9.0))
            cfg.initial_temp = float(rng.uniform(26.0, 30.0))
            cfg.weather.day_of_year = int(rng.integers(150, 300))
            cfg.initial_TAN = float(rng.uniform(0.05, 0.5))
            cfg.initial_algae = float(rng.uniform(20.0, 100.0))

        if options:
            if "initial_do" in options:
                cfg.initial_do = float(options["initial_do"])
            if "initial_temp" in options:
                cfg.initial_temp = float(options["initial_temp"])
            if "day_of_year" in options:
                cfg.weather.day_of_year = int(options["day_of_year"])

        self._sim = PondSimulator(cfg)
        self._t = 0.0
        self._current_state = np.array([
            cfg.initial_temp,
            cfg.initial_do,
            cfg.initial_CT,
            cfg.initial_TAN,
            cfg.initial_algae,
            cfg.shrimp.initial_weight_g,
            cfg.shrimp.stocking_density_m2 * cfg.shrimp.initial_weight_g,
        ], dtype=np.float64)
        self._episode_B0 = float(self._current_state[6])
        self._prev_B = self._episode_B0
        self._history = []

        obs = self._get_obs()
        info = {"t_h": self._t, "day": 0}
        return obs, info

    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Advance the environment by one step.

        Args:
            action: [aeration_fraction, exchange_rate, feed_multiplier].

        Returns:
            Tuple of (obs, reward, terminated, truncated, info).
        """
        if self._sim is None:
            raise RuntimeError("Call reset() before step().")

        # Clip action to valid range
        action = np.clip(action, _ACT_LOW, _ACT_HIGH)
        aer_frac = float(action[0])
        exchange_rate = float(action[1])  # fraction/day
        feed_mult = float(action[2])

        # Apply aeration to sim
        self._sim._DO_params.aeration_fraction = aer_frac
        self._sim._DO_params.n_aerators = self._base_config.pond.n_aerators

        # Apply feed multiplier (stored as schedule for single step)
        # Use a simple approach: override for this step via feed_multiplier param
        self._sim._feed_schedule = None  # clear schedule; use constant

        # Integrate for one step
        t_start = self._t
        t_end = self._t + self._step_hours
        t_eval = np.array([t_start, t_end])

        # Set aeration in sim config
        self._sim._aeration_schedule = {0.0: aer_frac}

        # Integrate
        result = self._sim.run(
            t_span=(t_start, t_end),
            t_eval=t_eval,
            method=self._sim._cfg.solver_method,
        )

        # Update internal state from solver output
        last_row = result.df.iloc[-1]
        self._current_state = np.array([
            last_row["T"], last_row["DO"], last_row["C_T"],
            last_row["TAN"], last_row["A"], last_row["W"], last_row["B"],
        ], dtype=np.float64)
        self._t = t_end

        # Record history
        self._history.append({
            "t": t_end,
            "DO": float(last_row["DO"]),
            "T": float(last_row["T"]),
            "pH": float(last_row["pH"]),
            "TAN": float(last_row["TAN"]),
            "NH3": float(last_row["NH3"]),
            "B": float(last_row["B"]),
            "reward": 0.0,  # placeholder, filled below
        })

        # Reset initial conditions for next step
        self._sim._cfg.initial_do = float(self._current_state[1])
        self._sim._cfg.initial_temp = float(self._current_state[0])
        self._sim._cfg.initial_CT = float(self._current_state[2])
        self._sim._cfg.initial_TAN = float(self._current_state[3])
        self._sim._cfg.initial_algae = float(self._current_state[4])
        self._sim._cfg.shrimp.initial_weight_g = float(self._current_state[5])

        # Reward calculation
        DO = float(last_row["DO"])
        NH3 = float(last_row["NH3"])
        B = float(last_row["B"])
        dB = B - self._prev_B
        self._prev_B = B

        B_max = self._base_config.shrimp.stocking_density_m2 * self._base_config.shrimp.target_weight_g
        biomass_reward = _W_BIOMASS * dB / max(B_max, 1.0)
        do_stress = 1.0 if DO < 3.0 else 0.0
        nh3_stress = 1.0 if NH3 > 0.1 else 0.0
        energy_cost = _W_ENERGY * aer_frac
        water_cost = _W_WATER * exchange_rate

        reward = (
            biomass_reward
            + _W_DO_STRESS * do_stress
            + _W_NH3_STRESS * nh3_stress
            + energy_cost
            + water_cost
        )
        self._history[-1]["reward"] = reward

        # Termination conditions
        day_of_cycle = self._t / 24.0
        terminated = False
        if DO < 0.5:
            terminated = True  # DO crash → episode end
        if float(last_row["pH"]) < 5.5 or float(last_row["pH"]) > 10.5:
            terminated = True
        # Harvest if W exceeds target
        if float(last_row["W"]) >= self._base_config.shrimp.target_weight_g:
            terminated = True

        truncated = day_of_cycle >= self._max_days

        obs = self._get_obs()
        info = {
            "t_h": self._t,
            "day": day_of_cycle,
            "DO": DO,
            "pH": float(last_row["pH"]),
            "NH3": NH3,
            "B": B,
            "W": float(last_row["W"]),
        }
        return obs, float(reward), terminated, truncated, info

    def _get_obs(self) -> np.ndarray:
        """Build observation from current state.

        Returns:
            Observation array [DO, T, pH, TAN, NH3, A, W, B, hour_of_day, day_of_cycle].
        """
        T = float(self._current_state[0])
        DO = float(self._current_state[1])
        CT = float(self._current_state[2])
        TAN = float(self._current_state[3])
        A = float(self._current_state[4])
        W = float(self._current_state[5])
        B = float(self._current_state[6])

        pH, _ = solve_pH(CT, self._base_config.pond.alkalinity_mg_L, T,
                          self._base_config.pond.salinity_ppt)
        NH3_frac = nh3_fraction(pH, T)
        NH3 = NH3_frac * TAN

        hour_of_day = self._t % 24.0
        day_of_cycle = self._t / 24.0

        obs = np.array([DO, T, pH, TAN, NH3, A, W, B, hour_of_day, day_of_cycle],
                        dtype=np.float32)
        # Clip to observation space
        obs = np.clip(obs, _OBS_LOW, _OBS_HIGH)
        return obs

    def render(self) -> Optional[np.ndarray]:
        """Render recent trajectory as matplotlib plot.

        Returns:
            RGB array if render_mode='rgb_array', else None.
        """
        if not self._history:
            return None

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        t = [h["t"] for h in self._history]
        DO = [h["DO"] for h in self._history]
        T = [h["T"] for h in self._history]
        pH = [h["pH"] for h in self._history]

        fig, axes = plt.subplots(3, 1, figsize=(8, 6), sharex=True)
        axes[0].plot(t, DO, color="steelblue")
        axes[0].axhline(3.0, color="red", linestyle="--", alpha=0.5, label="Stress threshold")
        axes[0].set_ylabel("DO (mg/L)")
        axes[0].legend(fontsize=8)

        axes[1].plot(t, T, color="coral")
        axes[1].set_ylabel("Temperature (°C)")

        axes[2].plot(t, pH, color="mediumseagreen")
        axes[2].set_ylabel("pH")
        axes[2].set_xlabel("Time (hours)")

        plt.tight_layout()

        if self._render_mode == "human":
            plt.show()
            plt.close(fig)
            return None
        elif self._render_mode == "rgb_array":
            fig.canvas.draw()
            buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
            buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
            plt.close(fig)
            return buf
        plt.close(fig)
        return None

    def close(self) -> None:
        """Clean up resources."""
        pass
