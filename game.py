"""Core game logic for the pig runner.

Pure Python: no pygame, no gym, no RL dependencies. This module is imported
inside ParallelEnv subprocesses, so it must stay import-light.

Units are native-canvas pixels. +y is down, so a negative vy means rising.
"""

import random

import config as C
import hazards as H
import world as W

DT = W.DT

# --- Motion -----------------------------------------------------------------
GRAVITY = 900.0                # px/sec^2
JUMP_V = 300.0                 # initial upward velocity (apex ~50px held)
JUMP_CUT = 0.8                 # releasing while rising scales vy (apex ~29px tapped, 47px held)

# --- Hazard spacing, expressed in time so it stays fair as speed ramps -----
MIN_GAP_SEC, MAX_GAP_SEC = 1.0, 1.6

# --- Hitbox insets (collision box is smaller than the art, so near misses read
# as near misses instead of feeling stolen) ----------------------------------
PIG_INSET = 2

# --- Observation normalisation ---------------------------------------------
OBS_DIST_SCALE = float(W.NATIVE_W)
OBS_HEIGHT_SCALE = 64.0
DIST_CLIP_LO, DIST_CLIP_HI = -0.5, 1.5

ACTION_NOOP = 0
ACTION_JUMP = 1
ACTION_DUCK = 2
NUM_ACTIONS = 3
OBS_DIM = 9


def _clip(v):
    return max(DIST_CLIP_LO, min(DIST_CLIP_HI, v))


def _dist_to(x):
    return _clip((x - W.PIG_X) / OBS_DIST_SCALE)


def _first_ahead(items):
    """First item in a scroll-ordered list that hasn't fully passed the pig."""
    for item in items:
        if item.right >= W.PIG_X:
            return item
    return None


class PigRunner:
    """The game itself. Advance it with step(action); read state off the attrs."""

    def __init__(self, seed=0):
        self._rng = random.Random(seed)
        self.reset()

    # -- lifecycle ----------------------------------------------------------
    def reset(self, seed=None):
        if seed is not None:
            self._rng.seed(seed)
        self.pig_y = float(W.PIG_GROUND_Y)
        self.vy = 0.0
        self.on_ground = True
        self.ducking = False
        self.hazards = [H.Bush(float(W.FIRST_X))]
        self.platforms = []
        self._speed = C.BASE_SPEED
        self._next_gap_px = self._sample_gap_px()
        self.score = 0
        self.steps = 0
        self.dead = False
        return self.observation()

    def _sample_gap_px(self):
        return self._rng.uniform(MIN_GAP_SEC, MAX_GAP_SEC) * self._speed

    def _current_speed(self):
        if not C.ENABLE_SPEED_RAMP:
            return C.BASE_SPEED
        t = min(1.0, self.steps / C.RAMP_STEPS)
        return C.BASE_SPEED + t * (C.MAX_SPEED - C.BASE_SPEED)

    # -- simulation ---------------------------------------------------------
    def step(self, action):
        """Advance one tick. Returns reward earned this tick."""
        if self.dead:
            return 0.0

        self._speed = self._current_speed()
        jump_held = action == ACTION_JUMP
        self.ducking = action == ACTION_DUCK and self.on_ground

        # Variable-height jump: press to launch, release while rising to cut it
        # short. No hidden timers -- vy and on_ground fully describe the arc.
        if jump_held and self.on_ground:
            self.vy = -JUMP_V
            self.on_ground = False
        elif not jump_held and self.vy < 0.0:
            self.vy *= JUMP_CUT

        prev_y = self.pig_y
        self.vy += GRAVITY * DT
        self.pig_y += self.vy * DT

        # Scroll the world, score anything that has gone by, retire what is off
        # screen, and spawn ahead as needed.
        dx = self._speed * DT
        reward = 0.0
        for hz in self.hazards:
            hz.update(dx)
            if not hz.passed and hz.right < W.PIG_X:
                hz.passed = True
                self.score += 1
                reward += 1.0
        for p in self.platforms:
            p.update(dx)

        self.hazards = [h for h in self.hazards if h.right >= 0.0]
        self.platforms = [p for p in self.platforms if p.right >= 0.0]

        if not self.hazards or (W.SPAWN_X - self.hazards[-1].x) >= self._next_gap_px:
            hz, plat = H.spawn_next(float(W.SPAWN_X), self._rng)
            self.hazards.append(hz)
            if plat is not None:
                self.platforms.append(plat)
            self._next_gap_px = self._sample_gap_px()

        # Landing: normally the real ground, but if the pig is already at or
        # above a platform it currently overlaps, land on that instead. The
        # "at or above" gate (checked against prev_y, before this frame's
        # fall) is what stops a pig walking on real ground from being
        # snapped upward just because a platform happens to scroll overhead.
        landing_y = float(W.PIG_GROUND_Y)
        plat = self._active_platform()
        if plat is not None and prev_y <= plat.surface_y:
            landing_y = plat.surface_y

        if self.pig_y >= landing_y:
            self.pig_y = landing_y
            self.vy = 0.0
            self.on_ground = True
        else:
            self.on_ground = False

        if self._collides():
            self.dead = True

        self.steps += 1
        return reward

    def _active_platform(self):
        for p in self.platforms:
            if p.covers(W.PIG_X):
                return p
        return None

    def _collides(self):
        px, py, pw, ph = self.pig_hitbox
        for hz in self.hazards:
            bx, by, bw, bh = hz.hitbox
            if px < bx + bw and px + pw > bx and py < by + bh and py + ph > by:
                return True
        return False

    # -- observation --------------------------------------------------------
    def next_hazard(self):
        return _first_ahead(self.hazards)

    def _next_platform(self):
        return _first_ahead(self.platforms)

    def observation(self):
        """The numbers the agent sees. Never pixels."""
        hz = self.next_hazard()
        if hz is None:
            dist, h_bottom, h_top = DIST_CLIP_HI, 0.0, 0.0
        else:
            dist = _dist_to(hz.x)
            h_bottom = hz.bottom_band / OBS_HEIGHT_SCALE
            h_top = hz.top_band / OBS_HEIGHT_SCALE

        plat = self._next_platform()
        if plat is None:
            p_dist, p_height = DIST_CLIP_HI, 0.0
        else:
            p_dist = _dist_to(max(plat.x_start, float(W.PIG_X)))
            p_height = plat.height / OBS_HEIGHT_SCALE

        height = (W.PIG_GROUND_Y - self.pig_y) / OBS_HEIGHT_SCALE
        vel = -self.vy / JUMP_V
        speed_span = C.MAX_SPEED - C.BASE_SPEED
        speed_norm = (self._speed - C.BASE_SPEED) / speed_span if speed_span > 0 else 0.0

        return [
            float(dist), float(height), float(vel), 1.0 if self.on_ground else 0.0,
            float(speed_norm), float(h_bottom), float(h_top),
            float(p_dist), float(p_height),
        ]

    @property
    def speed(self):
        return self._speed

    @property
    def pig_hitbox(self):
        if self.ducking:
            top, h = self.pig_y + (W.PIG_H - W.DUCK_H), W.DUCK_H
        else:
            top, h = self.pig_y, W.PIG_H
        return (
            W.PIG_X + PIG_INSET,
            top + PIG_INSET,
            W.PIG_W - 2 * PIG_INSET,
            h - 2 * PIG_INSET,
        )
