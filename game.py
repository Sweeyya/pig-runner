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
# GRAVITY and JUMP_V are scaled down together (both x0.85) from the original
# 4x-scale values (3600/1200) -- playtesting found the full-height jump
# (~188px apex) felt too high. Scaling both by the same factor shrinks the
# apex (~160px now) while leaving the jump's *duration* exactly unchanged
# (duration ~ v/g, apex ~ v^2/g -- scaling both by k scales apex by k^2 but
# leaves the v/g ratio, and so duration, untouched), so every timing window
# tuned elsewhere in this file and in play.py stays valid. This isn't a free
# knob, though: 0.85 was found empirically to be the lowest safe value --
# 0.8 (apex ~150px) already breaks reliably landing on a platform (its
# entry timing window assumes reaching PLATFORM_HEIGHT=120 with real margin
# to spare; verified via the standard 500-seed sweep, which drops from
# 500/500 at 0.85 to 24/500 at 0.8).
GRAVITY = 3060.0                # px/sec^2 -- 3600 x 0.85
JUMP_V = 1020.0                 # px/sec -- 1200 x 0.85
# Single fixed-height jump, Chrome-Dino style -- no hold-for-higher mechanic.
# A variable-height jump was tried and dropped: our bush is wide enough that
# reliably clearing it needs an arc that stays up almost as long as a full
# jump anyway, so a genuinely shorter/lower "tap" can't reliably clear it at
# any speed -- there's no real middle height to hold for. Distinguishing
# hazards is done by *when* you jump (see play.py's press-time windows),
# not by how long you hold the button once you have.

# --- Hazard spacing, expressed in time so it stays fair as speed ramps -----
# MIN_GAP_SEC has a real floor: a platform can reach ~184px ahead of its own
# bush, and dismounting one is a ~13-step fall (from PLATFORM_HEIGHT) before
# a ground hazard is even reactable again. Too short a gap can put the next
# hazard's own trigger window inside that fall, guaranteeing a late landing.
MIN_GAP_SEC, MAX_GAP_SEC = 1.4, 2.0

# --- Hitbox insets (collision box is smaller than the art, so near misses read
# as near misses instead of feeling stolen) ----------------------------------
PIG_INSET = 8

# --- Observation normalisation ---------------------------------------------
OBS_DIST_SCALE = float(W.NATIVE_W)
OBS_HEIGHT_SCALE = 256.0
DIST_CLIP_LO, DIST_CLIP_HI = -0.5, 1.5

ACTION_NOOP = 0
ACTION_JUMP = 1
NUM_ACTIONS = 2
OBS_DIM = 11


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


def _bands(hz):
    """A hazard's (bottom, top) height band, normalized -- 0/0 if there's no
    hazard at all, shared by the ground and platform-deck lanes since both
    read the same two fields off whatever's ahead."""
    if hz is None:
        return 0.0, 0.0
    return hz.bottom_band / OBS_HEIGHT_SCALE, hz.top_band / OBS_HEIGHT_SCALE


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
        self.hazards = [H.Bush(float(W.FIRST_X))]
        self.platforms = []
        self._speed = C.BASE_SPEED
        self._last_spawn_x = float(W.FIRST_X)
        self._prev_was_platform = False
        self._next_plan = H.plan_next(self._rng)
        self._next_gap_px = self._sample_gap_px()
        self.score = 0
        self.steps = 0
        self.dead = False
        return self.observation()

    def _sample_gap_px(self):
        base = self._rng.uniform(MIN_GAP_SEC, MAX_GAP_SEC) * self._speed
        return base + H.extra_gap_px(self._next_plan, self._prev_was_platform, self._speed)

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

        # Fixed-height jump: pressing while grounded launches the full arc.
        # Holding or releasing afterward does nothing -- on_ground already
        # fully describes whether another press can launch a new one.
        if action == ACTION_JUMP and self.on_ground:
            self.vy = -JUMP_V
            self.on_ground = False

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
                reward += 1.0
        for p in self.platforms:
            p.update(dx)
        self._last_spawn_x -= dx

        self.hazards = [h for h in self.hazards if h.right >= 0.0]
        self.platforms = [p for p in self.platforms if p.right >= 0.0]

        if (W.SPAWN_X - self._last_spawn_x) >= self._next_gap_px:
            hz, plat = H.materialize(self._next_plan, float(W.SPAWN_X), self._rng)
            self.hazards.append(hz)
            # A platform can physically extend past whatever hazard sits on
            # or under it (its own trailing margin beyond a deck hazard, or
            # the margin beyond a plain ground bush) -- the next gap must be
            # measured from that real rightmost extent, not just the hazard's
            # x, or the pig can still be riding the platform well after the
            # gap "should" have elapsed.
            self._last_spawn_x = hz.x
            if plat is not None:
                self.platforms.append(plat)
                if plat.deck_hazard is not None:
                    self.hazards.append(plat.deck_hazard)
                self._last_spawn_x = max(self._last_spawn_x, plat.x_end)
            self._prev_was_platform = plat is not None
            self._next_plan = H.plan_next(self._rng)
            self._next_gap_px = self._sample_gap_px()

        # Landing: normally the real ground, but if the pig is already at or
        # above a platform it currently overlaps, land on that instead. The
        # "at or above" gate (checked against prev_y, before this frame's
        # fall) is what stops a pig walking on real ground from being
        # snapped upward just because a platform happens to scroll overhead.
        # Both targets are the pig's *top-left* landing position, so a
        # platform target must subtract PIG_H the same way W.PIG_GROUND_Y
        # already does for the ground -- landing_y is where the pig's feet
        # end up, not where its head is.
        landing_y = float(W.PIG_GROUND_Y)
        plat = self._active_platform()
        if plat is not None and prev_y <= plat.surface_y - W.PIG_H:
            landing_y = plat.surface_y - W.PIG_H

        if self.pig_y >= landing_y:
            self.pig_y = landing_y
            self.vy = 0.0
            self.on_ground = True
        else:
            self.on_ground = False

        if self._collides():
            self.dead = True

        self.steps += 1
        # Displayed score is seconds survived, not hazards cleared -- ticks
        # up continuously like an endless-runner distance counter, instead
        # of sitting still between hazards. Purely a HUD number: the RL
        # reward above is untouched, still +1 per hazard cleared.
        self.score = self.steps // int(W.FPS)
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
        """Next hazard on the ground lane (not sitting on a platform deck)."""
        return _first_ahead([h for h in self.hazards if not h.on_platform])

    def _next_platform(self):
        return _first_ahead(self.platforms)

    def next_platform_hazard(self):
        """Next hazard on a platform's deck, if any -- a separate lane from
        the ground, since both can be relevant to choose between at once."""
        return _first_ahead([h for h in self.hazards if h.on_platform])

    def observation(self):
        """The numbers the agent sees. Never pixels."""
        hz = self.next_hazard()
        dist = _dist_to(hz.x) if hz is not None else DIST_CLIP_HI
        h_bottom, h_top = _bands(hz)

        plat = self._next_platform()
        if plat is None:
            p_dist, p_height = DIST_CLIP_HI, 0.0
        else:
            p_dist = _dist_to(max(plat.x_start, float(W.PIG_X)))
            p_height = plat.height / OBS_HEIGHT_SCALE

        ph_bottom, ph_top = _bands(self.next_platform_hazard())

        height = (W.PIG_GROUND_Y - self.pig_y) / OBS_HEIGHT_SCALE
        vel = -self.vy / JUMP_V
        speed_span = C.MAX_SPEED - C.BASE_SPEED
        speed_norm = (self._speed - C.BASE_SPEED) / speed_span if speed_span > 0 else 0.0

        return [
            float(dist), float(height), float(vel), 1.0 if self.on_ground else 0.0,
            float(speed_norm), float(h_bottom), float(h_top),
            float(p_dist), float(p_height), float(ph_bottom), float(ph_top),
        ]

    @property
    def speed(self):
        return self._speed

    @property
    def pig_hitbox(self):
        return (
            W.PIG_X + PIG_INSET,
            self.pig_y + PIG_INSET,
            W.PIG_W - 2 * PIG_INSET,
            W.PIG_H - 2 * PIG_INSET,
        )
