"""r2dreamer-compatible environment wrapper.

Matches the interface in NM512/r2dreamer (envs/crafter.py, envs/dmc.py):
subclasses gym.Env and uses gym.spaces, but with old-gym call signatures --
reset() returns the obs dict alone, step() returns a 4-tuple, and the obs dict
carries is_first / is_last / is_terminal.

The episode cap is NOT implemented here: r2dreamer's wrappers.TimeLimit owns it
(configure time_limit: 1000). We only report true death, via info["discount"]=0,
so hitting the cap stays a truncation and death stays a termination.

Deliberately never imports pygame -- ParallelEnv constructs this in subprocesses.
"""

import gymnasium as gym
import numpy as np

try:  # works both standalone and when copied into r2dreamer's envs/ package
    from .game import NUM_ACTIONS, OBS_DIM, PigRunner
except ImportError:
    from game import NUM_ACTIONS, OBS_DIM, PigRunner


class PigRunnerEnv(gym.Env):
    metadata = {}

    def __init__(self, task="v0", seed=0):
        assert task == "v0", f"only the v0 task exists so far, got {task!r}"
        self._game = PigRunner(seed=seed)
        self.reward_range = [-np.inf, np.inf]

    @property
    def observation_space(self):
        return gym.spaces.Dict(
            {"state": gym.spaces.Box(-np.inf, np.inf, (OBS_DIM,), dtype=np.float32)}
        )

    @property
    def action_space(self):
        # make_env wraps this in wrappers.OneHotAction; we receive a plain int.
        return gym.spaces.Discrete(NUM_ACTIONS)

    def _obs(self, is_first=False, is_last=False, is_terminal=False):
        return {
            "state": np.asarray(self._game.observation(), dtype=np.float32),
            "is_first": is_first,
            "is_last": is_last,
            "is_terminal": is_terminal,
        }

    def reset(self):
        self._game.reset()
        return self._obs(is_first=True)

    def step(self, action):
        reward = self._game.step(int(action))
        dead = self._game.dead
        # discount 0 marks a real terminal state. TimeLimit injects 1.0 when it
        # ends the episode on the step cap, which keeps that a truncation.
        info = {"discount": np.array(0.0 if dead else 1.0, dtype=np.float32)}
        obs = self._obs(is_last=dead, is_terminal=dead)
        return obs, np.float32(reward), dead, info

    def render(self):
        try:  # works both standalone and when copied into r2dreamer's envs/ package
            from .render import render_rgb
        except ImportError:
            from render import render_rgb

        return render_rgb(self._game)
