"""Shared world constants. No logic here -- just numbers both game.py and
hazards.py need, kept separate so neither has to import the other.

Spatial sizes are 2x the original v0/v1 scale, so 32x32 sprite art shows
real detail instead of being squashed into a 16x16 box. Physics constants
in game.py are scaled the same way, which keeps every existing tuning
(jump windows, hazard clearances, reaction times) identical in *seconds*
-- only the pixel numbers changed, not the feel.

The canvas height is deliberately short: the tallest thing that ever needs
to be on screen is the pig at max jump apex (~132px above ground). The
original 360 left ~130px of sky above that clearance line that nothing
ever used -- pure wasted space that made the pig and every hazard look
tiny relative to the window.
"""

FPS = 50
DT = 1.0 / FPS

NATIVE_W, NATIVE_H = 640, 240
SCALE = 3                      # window is 1920x720
TILE = 32
GROUND_Y = 150                 # y of the ground surface

PIG_X = 96                     # pig is fixed in x; the world scrolls past it
PIG_W, PIG_H = 32, 32
PIG_GROUND_Y = GROUND_Y - PIG_H
DUCK_H = 16                    # crouched height; pig's feet stay planted

SPAWN_X = NATIVE_W + 80
FIRST_X = NATIVE_W + 120       # extra room before the first hazard
