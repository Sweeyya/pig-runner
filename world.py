"""Shared world constants. No logic here -- just numbers both game.py and
hazards.py need, kept separate so neither has to import the other.

Spatial sizes are 4x the original v0/v1 scale (2x, then another 2x after
the first pass still looked too small/pixelated on screen -- the ceiling on
visible detail is the final on-screen pixel size, not the source art
resolution, so there was no way around growing this again). Physics
constants in game.py are scaled the same way, which keeps every existing
tuning (jump windows, hazard clearances, reaction times) identical in
*seconds* -- only the pixel numbers changed, not the feel.

Canvas height was originally sized to the minimum needed to show the pig
at max jump apex (~264px above ground) plus a small buffer. Jump height
was later tuned down (see game.py's GRAVITY/JUMP_V) to ~160px apex after
playtesting found the original felt too high, without shrinking the canvas
to match -- the extra headroom just reads as more sky now, which is fine,
rather than re-deriving every asset/window size that depends on NATIVE_H.
The margin below ground for the dirt band is still kept thin regardless --
that band is pure decoration, so it doesn't get to compete for screen
space the way the sky's jump-clearance requirement does.
"""

FPS = 50
DT = 1.0 / FPS

NATIVE_W, NATIVE_H = 640, 360
SCALE = 3                      # window is 1920x1080
TILE = 64
GROUND_Y = 300                 # y of the ground surface

PIG_X = 96                     # pig is fixed in x; the world scrolls past it
PIG_W, PIG_H = 64, 64
PIG_GROUND_Y = GROUND_Y - PIG_H

SPAWN_X = NATIVE_W + 80
FIRST_X = NATIVE_W + 120       # extra room before the first hazard
