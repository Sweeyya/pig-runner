"""Hazard types and the spawn registry. Each hazard is a small self-contained
class; toggling one off in config.py just removes it from the weighted
choices below -- nothing else needs to change.

Every hazard exposes:
  .x, .w              -- world position and width (scrolls via .update(dx))
  .hitbox             -- (x, y, w, h) collision rect, inset from the art
  .bottom_band/.top_band -- height above ground the hazard occupies (px),
                            0 = touches the ground. This is what the agent
                            observes -- a continuous "what's coming" signal,
                            not a type label -- so jump-vs-duck-vs-height is
                            a numeric decision, never a hidden one.

Platforms are terrain, not hazards: they're never checked for collision
(see game.py's landing logic) and only ever pair with a Bush, positioned
well above jump-clearing height for one, so there is always a real ground
route underneath.
"""

import config as C
import world as W

# --- Geometry ---------------------------------------------------------------
# Every number here is 2x the original v0/v1 tuning, matching world.py and
# game.py's 2x scale-up -- same relative clearances, just more sprite detail.
BUSH_W, BUSH_H = 32, 24                  # tap-jump clears this
TALL_W, TALL_H = 32, 72                  # needs a held jump (tap apex ~34 < 72 < hold apex ~94)
SNOW_W, SNOW_H = 24, 24                  # visual size of the snowball sprite
SNOW_LOW_BAND = (0.0, 28.0)              # grounded -- jump clears it, like a bush
SNOW_HIGH_BAND = (20.0, 104.0)           # floating band no jump reaches -- duck required

PLATFORM_THICKNESS = 12
PLATFORM_MARGIN = 152.0                   # generous -- covers the full above-height window even at max speed

# Hitbox insets so near-misses read as near-misses, not stolen deaths.
BOX_INSET_X, BOX_INSET_TOP = 6, 4         # shared by every ground-standing box hazard
SNOW_INSET = 2


class Hazard:
    kind = "hazard"
    inset_x, inset_top = 0, 0

    def __init__(self, x):
        self.x = x
        self.passed = False

    def update(self, dx):
        self.x -= dx

    @property
    def right(self):
        return self.x + self.w

    @property
    def hitbox(self):
        """Default shape for a box sitting on the ground, inset from the art.
        Snowball overrides this -- its box floats at a band instead."""
        return (
            self.x + self.inset_x,
            W.GROUND_Y - self.h + self.inset_top,
            self.w - 2 * self.inset_x,
            self.h - self.inset_top,
        )


class Bush(Hazard):
    kind = "bush"
    w, h = BUSH_W, BUSH_H
    inset_x, inset_top = BOX_INSET_X, BOX_INSET_TOP
    bottom_band, top_band = 0.0, float(BUSH_H)


class TallObstacle(Hazard):
    kind = "tall_obstacle"
    w, h = TALL_W, TALL_H
    inset_x, inset_top = BOX_INSET_X, BOX_INSET_TOP
    bottom_band, top_band = 0.0, float(TALL_H)


class Snowball(Hazard):
    kind = "snow_golem"
    w, h = SNOW_W, SNOW_H

    def __init__(self, x, high):
        super().__init__(x)
        self.high = high
        self.bottom_band, self.top_band = SNOW_HIGH_BAND if high else SNOW_LOW_BAND

    @property
    def hitbox(self):
        y = W.GROUND_Y - self.top_band + SNOW_INSET
        h = (self.top_band - self.bottom_band) - 2 * SNOW_INSET
        return (self.x + SNOW_INSET, y, self.w - 2 * SNOW_INSET, h)


class Platform:
    """Terrain, not a hazard -- never collided with directly. Spans a Bush,
    floating well above tap-jump height, so the ground route always exists.
    """

    kind = "platform"

    def __init__(self, x_start, x_end, height):
        self.x_start = x_start
        self.x_end = x_end
        self.height = height       # px above ground the walkable surface sits

    def update(self, dx):
        self.x_start -= dx
        self.x_end -= dx

    def covers(self, x):
        return self.x_start <= x <= self.x_end

    @property
    def right(self):
        return self.x_end

    @property
    def surface_y(self):
        return W.GROUND_Y - self.height


_TYPES = {
    "bush": lambda x, rng: Bush(x),
    "tall_obstacle": lambda x, rng: TallObstacle(x),
    "snow_golem": lambda x, rng: Snowball(x, high=rng.random() < 0.5),
}


def _enabled_weights():
    weights = {"bush": C.SPAWN_WEIGHTS.get("bush", 1)}
    if C.ENABLE_TALL_OBSTACLE:
        weights["tall_obstacle"] = C.SPAWN_WEIGHTS.get("tall_obstacle", 1)
    if C.ENABLE_SNOW_GOLEM:
        weights["snow_golem"] = C.SPAWN_WEIGHTS.get("snow_golem", 1)
    return weights


def spawn_next(x, rng):
    """Return (hazard, platform_or_None) for the next spawn point."""
    weights = _enabled_weights()
    kinds = list(weights)
    picks = [weights[k] for k in kinds]
    kind = rng.choices(kinds, weights=picks, k=1)[0]
    hazard = _TYPES[kind](x, rng)

    platform = None
    if (
        C.ENABLE_PLATFORMS
        and kind == "bush"
        and rng.random() < C.PLATFORM_CHANCE
    ):
        platform = Platform(
            x_start=x - PLATFORM_MARGIN,
            x_end=x + BUSH_W + PLATFORM_MARGIN,
            height=C.PLATFORM_HEIGHT,
        )
    return hazard, platform
