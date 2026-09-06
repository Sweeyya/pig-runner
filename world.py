"""Shared world constants. No logic here -- just numbers both game.py and
hazards.py need, kept separate so neither has to import the other.
"""

FPS = 50
DT = 1.0 / FPS

NATIVE_W, NATIVE_H = 320, 180
SCALE = 4                      # window is 1280x720
TILE = 16
GROUND_Y = 140                 # y of the ground surface

PIG_X = 48                     # pig is fixed in x; the world scrolls past it
PIG_W, PIG_H = 16, 16
PIG_GROUND_Y = GROUND_Y - PIG_H
DUCK_H = 8                     # crouched height; pig's feet stay planted

SPAWN_X = NATIVE_W + 40
FIRST_X = NATIVE_W + 60        # extra room before the first hazard
