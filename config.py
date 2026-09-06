"""Toggle hazards and tune difficulty here. No code changes needed elsewhere --
flip a flag, run play.py, get a different game.

Disabling every ENABLE_* flag reproduces exactly the v0 game (bush only,
fixed speed).
"""

# --- Hazards ------------------------------------------------------------
ENABLE_TALL_OBSTACLE = True
ENABLE_SNOW_GOLEM = True
ENABLE_PLATFORMS = True

# Relative spawn weights among whatever hazards are enabled. The bush is
# always available as the baseline.
SPAWN_WEIGHTS = {
    "bush": 3,
    "tall_obstacle": 2,
    "snow_golem": 2,
}

# --- Speed ramp -----------------------------------------------------------
# px/sec values are 2x the original v0/v1 tuning, matching world.py's 2x
# spatial scale -- RAMP_STEPS is a step count, not a distance, so it's
# untouched and the ramp still takes the same real time.
ENABLE_SPEED_RAMP = True
BASE_SPEED = 400.0      # px/sec at episode start
MAX_SPEED = 680.0       # px/sec ceiling
RAMP_STEPS = 700.0      # steps to go from BASE_SPEED to MAX_SPEED

# --- Platforms --------------------------------------------------------
# A platform spans a hazard, giving an alternate route: jump onto it, run
# across, drop back down, instead of timing a jump over the hazard itself.
PLATFORM_CHANCE = 0.5   # fraction of eligible hazards that get one
PLATFORM_HEIGHT = 68.0  # px above ground the platform surface sits
