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
# Pace is a gameplay-feel choice, independent of the world's pixel scale --
# kept at the original v0 pace (not doubled along with everything spatial)
# since a human found the doubled speed too fast to react to.
ENABLE_SPEED_RAMP = True
BASE_SPEED = 200.0      # px/sec at episode start
MAX_SPEED = 340.0       # px/sec ceiling
RAMP_STEPS = 700.0      # steps to go from BASE_SPEED to MAX_SPEED

# --- Platforms --------------------------------------------------------
# A platform spans a hazard, giving an alternate route: jump onto it, run
# across, drop back down, instead of timing a jump over the hazard itself.
# Height is well below the hold-jump apex (~188px) on purpose -- a human
# doesn't time a jump as precisely as a script, so landing on top should
# only need "a decent jump", not "an exactly-held max-height jump". 96 is
# also the floor for a different reason: any lower and a pig resting on
# the deck vertically overlaps the bush hitbox underneath it -- 120 keeps
# a 24px margin above that floor.
PLATFORM_CHANCE = 0.5   # fraction of eligible hazards that get one
PLATFORM_HEIGHT = 120.0  # px above ground the platform surface sits
