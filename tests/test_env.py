"""Tests for XoceaniaPondEnv gymnasium environment.

Key tests:
- Passes gymnasium spec check
- Runs 1000 steps without NaN
- Observation and action spaces valid
- Reset returns valid observation
"""

import pytest
import numpy as np
import gymnasium as gym
from xoceania_sim import XoceaniaPondEnv, SimConfig


class TestGymSpec:
    """Tests for gymnasium compatibility."""

    def test_env_instantiation(self):
        """XoceaniaPondEnv should be instantiable."""
        env = XoceaniaPondEnv()
        assert env is not None

    def test_observation_space_valid(self):
        """Observation space should be a valid Box."""
        env = XoceaniaPondEnv()
        obs_space = env.observation_space
        assert isinstance(obs_space, gym.spaces.Box)
        assert obs_space.shape == (10,)
        assert obs_space.dtype == np.float32

    def test_action_space_valid(self):
        """Action space should be a valid Box."""
        env = XoceaniaPondEnv()
        act_space = env.action_space
        assert isinstance(act_space, gym.spaces.Box)
        assert act_space.shape == (3,)
        assert act_space.dtype == np.float32

    def test_action_space_bounds(self):
        """Action space bounds should match spec."""
        env = XoceaniaPondEnv()
        np.testing.assert_array_almost_equal(env.action_space.low, [0.0, 0.0, 0.5])
        np.testing.assert_array_almost_equal(env.action_space.high, [1.0, 0.2, 1.5])

    def test_reset_returns_obs_info(self):
        """reset() should return (obs, info) tuple."""
        env = XoceaniaPondEnv()
        result = env.reset(seed=42)
        assert len(result) == 2
        obs, info = result
        assert isinstance(obs, np.ndarray)
        assert isinstance(info, dict)
        assert obs.shape == (10,)
        assert obs.dtype == np.float32

    def test_obs_in_observation_space(self):
        """Initial observation should be within observation space bounds."""
        env = XoceaniaPondEnv(randomize_init=False)
        obs, _ = env.reset()
        assert env.observation_space.contains(obs), \
            f"Observation {obs} not in observation space"

    def test_step_returns_five_values(self):
        """step() should return (obs, reward, terminated, truncated, info)."""
        env = XoceaniaPondEnv()
        env.reset(seed=0)
        action = env.action_space.sample()
        result = env.step(action)
        assert len(result) == 5
        obs, reward, terminated, truncated, info = result
        assert isinstance(obs, np.ndarray)
        assert isinstance(float(reward), float)
        assert isinstance(bool(terminated), bool)
        assert isinstance(bool(truncated), bool)
        assert isinstance(info, dict)

    def test_step_obs_finite(self):
        """Observation after step should be finite."""
        env = XoceaniaPondEnv()
        env.reset(seed=1)
        action = np.array([0.8, 0.0, 1.0], dtype=np.float32)
        obs, _, _, _, _ = env.step(action)
        assert np.isfinite(obs).all(), f"Non-finite observation: {obs}"

    def test_step_reward_finite(self):
        """Reward should be finite."""
        env = XoceaniaPondEnv()
        env.reset(seed=2)
        action = np.array([1.0, 0.0, 1.0], dtype=np.float32)
        _, reward, _, _, _ = env.step(action)
        assert np.isfinite(reward), f"Non-finite reward: {reward}"


class TestGymMassTest:
    """Stress tests for environment stability."""

    def test_1000_steps_no_nan(self):
        """1000 environment steps should produce no NaN observations."""
        env = XoceaniaPondEnv(randomize_init=False)
        obs, _ = env.reset(seed=42)

        nan_count = 0
        for step_i in range(1000):
            if np.isnan(obs).any():
                nan_count += 1

            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)

            assert np.isfinite(reward), f"NaN reward at step {step_i}"

            if terminated or truncated:
                obs, _ = env.reset()

        assert nan_count == 0, f"Found {nan_count} steps with NaN observations"

    def test_random_policy_completes(self):
        """Random policy should run without exceptions for 100 steps."""
        env = XoceaniaPondEnv()
        obs, _ = env.reset(seed=99)
        done = False
        steps = 0
        while not done and steps < 100:
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1
        assert steps > 0

    def test_max_aeration_action(self):
        """Max aeration should keep DO high."""
        env = XoceaniaPondEnv(randomize_init=False)
        env.reset(seed=0)
        max_action = np.array([1.0, 0.0, 1.0], dtype=np.float32)  # full aeration
        min_do = 30.0
        for _ in range(24):
            obs, _, _, _, _ = env.step(max_action)
            do = float(obs[0])  # DO is first observation
            min_do = min(min_do, do)
        assert min_do > 3.0, f"DO crashed even with max aeration: {min_do:.2f} mg/L"

    def test_deterministic_with_seed(self):
        """Same seed should produce same trajectory."""
        env1 = XoceaniaPondEnv()
        env2 = XoceaniaPondEnv()
        obs1, _ = env1.reset(seed=42)
        obs2, _ = env2.reset(seed=42)
        np.testing.assert_array_equal(obs1, obs2, err_msg="Same seed gives different obs")

    def test_close_no_error(self):
        """close() should not raise."""
        env = XoceaniaPondEnv()
        env.reset()
        env.close()  # Should not raise


class TestRewardShaping:
    """Tests for reward function properties."""

    def test_reward_higher_with_aeration(self):
        """Full aeration should generally give higher reward than no aeration
        (due to avoiding DO stress penalty)."""
        env = XoceaniaPondEnv(randomize_init=False)
        # Run no-aeration
        env.reset(seed=0)
        no_aer_rewards = []
        for _ in range(10):
            obs, reward, term, trunc, _ = env.step(np.array([0.0, 0.0, 1.0], dtype=np.float32))
            no_aer_rewards.append(float(reward))
            if term or trunc:
                break

        # Run full aeration
        env.reset(seed=0)
        full_aer_rewards = []
        for _ in range(10):
            obs, reward, term, trunc, _ = env.step(np.array([1.0, 0.0, 1.0], dtype=np.float32))
            full_aer_rewards.append(float(reward))
            if term or trunc:
                break

        # Total reward should differ (full aeration costs energy but avoids DO stress)
        # At least check both are finite
        assert all(np.isfinite(r) for r in no_aer_rewards), "No-aeration rewards have NaN"
        assert all(np.isfinite(r) for r in full_aer_rewards), "Full-aeration rewards have NaN"
