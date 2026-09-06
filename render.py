"""Visual renderer. Imported only when something actually wants pixels --
never by the training path, which runs many envs in subprocesses.

Draws colored rectangles today. Drop PNGs into assets/ (see assets/README.md)
and they are picked up automatically, no renderer changes needed.
"""

import os

import numpy as np
import pygame

import world as W
from game import DIST_CLIP_HI, OBS_DIST_SCALE, OBS_HEIGHT_SCALE
from hazards import PLATFORM_THICKNESS

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Minecraft-leaning palette. Also the palette to draw the real art against.
SKY        = (135, 186, 227)
CLOUD      = (222, 238, 247)
GRASS_TOP  = (106, 170,  75)
GRASS_EDGE = ( 86, 140,  61)
DIRT       = (134,  96,  67)
DIRT_DARK  = (110,  78,  55)
PIG_PINK   = (241, 167, 178)
PIG_DARK   = (206, 129, 142)
PIG_SNOUT  = (224, 137, 152)
PIG_EYE    = ( 40,  30,  35)
BUSH_GREEN = ( 58, 110,  47)
BUSH_DARK  = ( 40,  82,  35)
BERRY_RED  = (191,  54,  46)
STONE      = (150, 150, 155)
STONE_DARK = (110, 110, 116)
SNOW_WHITE = (240, 246, 250)
SNOW_SHADE = (200, 215, 225)
GOLEM_NOSE = (219, 130,  40)
HITBOX     = (255,  64,  64)
BAND       = (255, 190,  60)
TEXT       = (250, 250, 250)
TEXT_BG    = (  0,   0,   0)
SCORE_COL  = (255, 255, 255)

# Animation frame counts -- the contract your sprite sheet must satisfy.
ANIM_FRAMES = {
    "run": 4, "rise": 1, "fall": 1, "land": 1, "death": 4,
    # reserved so v1/v2 art slots in without renumbering anything
    "mine": 4, "place": 3,
}
RUN_FPS = 12.0
DEATH_FPS = 10.0
LAND_STEPS = 4

_sprite_cache = {}


def load_sprite(name):
    """Return a Surface for assets/<name>.png, or None if it isn't there yet."""
    if name in _sprite_cache:
        return _sprite_cache[name]
    path = os.path.join(ASSET_DIR, name + ".png")
    surf = None
    if os.path.exists(path):
        surf = pygame.image.load(path).convert_alpha()
    _sprite_cache[name] = surf
    return surf


def has_sprites():
    return load_sprite("pig_run_00") is not None


_scaled_cache = {}


def _blit_sprite(surf, names, pos, size=None):
    """Draw the first existing assets/<name>.png at pos, scaled to `size` if
    given. `names` is a single name or a fallback list tried in order.
    Returns whether anything drew, so callers can fall back to the
    colored-rectangle version.

    Art is authored bigger than the game actually needs (see
    tools/build_sprites.py) and fitted down here at draw time, cached per
    (name, size) -- one clean downscale from real detail, rather than
    pre-shrinking files to the exact pixel box up front and losing
    whatever didn't survive that."""
    if isinstance(names, str):
        names = (names,)
    for name in names:
        sprite = load_sprite(name)
        if sprite is None:
            continue
        if size is not None and sprite.get_size() != size:
            key = (name, size)
            scaled = _scaled_cache.get(key)
            if scaled is None:
                scaled = pygame.transform.smoothscale(sprite, size)
                _scaled_cache[key] = scaled
            sprite = scaled
        surf.blit(sprite, pos)
        return True
    return False


class Animator:
    """Maps game state onto (animation, frame). Drives sprites and the
    rectangle fallback alike, so motion is visible before any art exists."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.anim, self.frame, self._t, self._land = "run", 0, 0.0, 0
        self._was_air = False

    def update(self, g):
        self._t += W.DT
        if g.dead:
            if self.anim != "death":
                self.anim, self._t = "death", 0.0
            self.frame = min(int(self._t * DEATH_FPS), ANIM_FRAMES["death"] - 1)
            return

        airborne = not g.on_ground
        if self._was_air and not airborne:
            self._land = LAND_STEPS
        self._was_air = airborne

        if airborne:
            self.anim = "rise" if g.vy < 0 else "fall"
            self.frame = 0
        elif self._land > 0:
            self._land -= 1
            self.anim, self.frame = "land", 0
        else:
            self.anim = "run"
            self.frame = int(self._t * RUN_FPS) % ANIM_FRAMES["run"]

    def squash(self):
        """Fallback-art stand-in for the squash/stretch the real sprites bake in."""
        if self.anim == "land":
            return 1.25, 0.75
        if self.anim == "rise":
            return 0.9, 1.1
        if self.anim == "fall":
            return 1.05, 0.95
        return 1.0, 1.0

    def bob(self):
        return 1 if (self.anim == "run" and self.frame in (1, 3)) else 0


def _draw_ground(surf):
    pygame.draw.rect(surf, GRASS_TOP, (0, W.GROUND_Y, W.NATIVE_W, 16))
    pygame.draw.rect(surf, GRASS_EDGE, (0, W.GROUND_Y + 16, W.NATIVE_W, 8))
    pygame.draw.rect(surf, DIRT, (0, W.GROUND_Y + 24, W.NATIVE_W, W.NATIVE_H - W.GROUND_Y - 24))
    for x in range(0, W.NATIVE_W, W.TILE):
        pygame.draw.line(surf, DIRT_DARK, (x, W.GROUND_Y + 24), (x, W.NATIVE_H))


def _draw_clouds(surf, scroll):
    for i, (cx, cy, w) in enumerate(((80, 60, 68), (300, 44, 52), (500, 76, 60))):
        # parallax: clouds drift at a fraction of world speed
        x = (cx - scroll * 0.25) % (W.NATIVE_W + 120) - 60
        pygame.draw.ellipse(surf, CLOUD, (x, cy, w, 20))
        pygame.draw.ellipse(surf, CLOUD, (x + w * 0.35, cy - 10, w * 0.6, 22))


def _draw_bush(surf, hz):
    x, y = int(hz.x), int(hz.surface_y - hz.h)
    if _blit_sprite(surf, "bush_00", (x, y), (hz.w, hz.h)):
        return
    pygame.draw.rect(surf, BUSH_DARK, (x, y, hz.w, hz.h))
    pygame.draw.rect(surf, BUSH_GREEN, (x + 1, y + 1, hz.w - 2, hz.h - 3))
    for bx, by in ((3, 4), (9, 3), (6, 8), (12, 7)):
        if bx < hz.w - 2 and by < hz.h - 2:
            pygame.draw.rect(surf, BERRY_RED, (x + bx, y + by, 2, 2))


def _draw_snow_golem(surf, hz):
    x, y = int(hz.x), int(hz.surface_y - hz.h)
    if _blit_sprite(surf, "snow_golem_00", (x, y), (hz.w, hz.h)):
        return
    # two stacked snow blocks (bigger below, smaller above) plus a small
    # pumpkin-orange nose -- reads as "snow golem", not just "tall block".
    w = hz.w
    lower_h = int(hz.h * 0.58)
    upper_h = hz.h - lower_h
    pygame.draw.rect(surf, SNOW_SHADE, (x, y + upper_h, w, lower_h))
    pygame.draw.rect(surf, SNOW_WHITE, (x + 3, y + upper_h + 3, w - 6, lower_h - 6))
    head_w = int(w * 0.8)
    hx = x + (w - head_w) // 2
    pygame.draw.rect(surf, SNOW_SHADE, (hx, y, head_w, upper_h))
    pygame.draw.rect(surf, SNOW_WHITE, (hx + 3, y + 3, head_w - 6, upper_h - 6))
    pygame.draw.rect(surf, GOLEM_NOSE, (hx + head_w - 6, y + upper_h // 2 - 2, 6, 4))


def _draw_platform(surf, p):
    # A grass block, not a wooden plank: green cap + dirt body, reusing the
    # exact ground palette so it reads as "the same grass," not a new material.
    x = int(p.x_start)
    w = int(p.x_end - p.x_start)
    y = int(p.surface_y)
    pygame.draw.rect(surf, GRASS_TOP, (x, y, w, 8))
    pygame.draw.rect(surf, GRASS_EDGE, (x, y + 8, w, 4))
    pygame.draw.rect(surf, DIRT, (x, y + 12, w, PLATFORM_THICKNESS - 12))


_HAZARD_DRAW = {
    "bush": _draw_bush,
    "snow_golem": _draw_snow_golem,
}


def _draw_pig(surf, g, anim):
    name = f"pig_{anim.anim}_{anim.frame:02d}"
    x, y = W.PIG_X, int(g.pig_y)
    if _blit_sprite(surf, (name, "pig_run_00"), (x, y), (W.PIG_W, W.PIG_H)):
        return

    sx, sy = anim.squash()
    w, h = int(W.PIG_W * sx), int(W.PIG_H * sy)
    x -= (w - W.PIG_W) // 2
    y += W.PIG_H - h + anim.bob()

    if anim.anim == "death":
        body = tuple(max(0, c - 30 * anim.frame) for c in PIG_PINK)
    else:
        body = PIG_PINK
    pygame.draw.rect(surf, body, (x, y, w, h))
    pygame.draw.rect(surf, PIG_DARK, (x, y + h - 3, w, 3))          # legs
    pygame.draw.rect(surf, PIG_SNOUT, (x + w - 4, y + h // 2 - 1, 4, 4))  # snout
    pygame.draw.rect(surf, PIG_DARK, (x + 2, y - 1, 3, 2))          # ear
    if anim.anim != "death":
        pygame.draw.rect(surf, PIG_EYE, (x + w - 7, y + 4, 2, 2))


def draw_world(surf, g, anim, scroll=0.0):
    surf.fill(SKY)
    _draw_clouds(surf, scroll)
    _draw_ground(surf)
    for p in g.platforms:
        _draw_platform(surf, p)
    for hz in g.hazards:
        _HAZARD_DRAW.get(hz.kind, _draw_bush)(surf, hz)
    _draw_pig(surf, g, anim)


# Blocky 3x5 digit font, drawn as solid squares rather than antialiased type
# -- reads as an 8-bit score counter (Chrome-dino-style), matching the rest
# of the game's chunky pixel-art look instead of a smooth system font.
_DIGIT_ROWS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}
DIGIT_CELL = 6        # px per block, at native (unscaled) resolution
DIGIT_GAP = 2 * DIGIT_CELL   # space between digits


def _digit_width():
    return 3 * DIGIT_CELL


def _draw_pixel_digits(surf, text, x, y, color=SCORE_COL):
    """Draw `text` (digits only) right there, one blocky glyph at a time."""
    for ch in text:
        for row, bits in enumerate(_DIGIT_ROWS[ch]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    surf.fill(color, (x + col * DIGIT_CELL, y + row * DIGIT_CELL, DIGIT_CELL, DIGIT_CELL))
        x += _digit_width() + DIGIT_GAP
    return x - DIGIT_GAP  # trailing edge, unused by callers today


def _pixel_digits_width(text):
    return len(text) * _digit_width() + (len(text) - 1) * DIGIT_GAP


def draw_hud(surf, g):
    """Always-on score readout -- separate from the toggleable debug overlay."""
    text = str(g.score)
    x = surf.get_width() - _pixel_digits_width(text) - 16
    _draw_pixel_digits(surf, text, x, 12)


DREAM_TINT = (60, 90, 180, 90)          # translucent blue wash over the whole frame
DREAM_PIG  = (150, 175, 235)
DREAM_HAZARD_LINE = (210, 225, 255)
DREAM_HAZARD_FILL = (120, 150, 220, 110)
DREAM_PLATFORM = (170, 190, 240, 130)
DREAM_LABEL = (215, 225, 255)


def _draw_dream_band(surf, x, y_top, y_bot, width):
    h = max(2.0, y_bot - y_top)
    band = pygame.Surface((width, h), pygame.SRCALPHA)
    band.fill(DREAM_HAZARD_FILL)
    surf.blit(band, (x, y_top))
    pygame.draw.rect(surf, DREAM_HAZARD_LINE, (x, y_top, width, h), 1)


def draw_dream(surf, obs, scroll=0.0, hazard_w=64.0):
    """Render a scene from *predicted* numbers instead of real game state --
    this is what the world model imagines, not what actually happened.

    obs is the 11-float vector game.py's observation() produces: the model
    predicts exactly these fields and nothing else, so this draws only what
    it could plausibly have predicted -- a generic hazard silhouette at the
    right distance and height band, never a specific sprite, since "which
    hazard is this" was never one of the numbers it predicted.
    """
    (dist, height, _vel, _on_ground, _speed, h_bottom, h_top,
     p_dist, p_height, ph_bottom, ph_top) = obs

    surf.fill(SKY)
    _draw_clouds(surf, scroll)
    _draw_ground(surf)

    has_platform = p_dist < DIST_CLIP_HI - 1e-3 and p_height > 1e-3
    if has_platform:
        px = W.PIG_X + p_dist * OBS_DIST_SCALE
        py = W.GROUND_Y - p_height * OBS_HEIGHT_SCALE
        deck = pygame.Surface((320, PLATFORM_THICKNESS), pygame.SRCALPHA)
        deck.fill(DREAM_PLATFORM)
        surf.blit(deck, (px - 160, py))
        if ph_top > 1e-3:
            hx = px - 160 + 160
            y_top = py - ph_top * OBS_HEIGHT_SCALE
            y_bot = py - ph_bottom * OBS_HEIGHT_SCALE
            _draw_dream_band(surf, hx, y_top, y_bot, hazard_w)

    if dist < DIST_CLIP_HI - 1e-3:
        hx = W.PIG_X + dist * OBS_DIST_SCALE
        y_top = W.GROUND_Y - h_top * OBS_HEIGHT_SCALE
        y_bot = W.GROUND_Y - h_bottom * OBS_HEIGHT_SCALE
        _draw_dream_band(surf, hx, y_top, y_bot, hazard_w)

    py = W.PIG_GROUND_Y - height * OBS_HEIGHT_SCALE
    pygame.draw.rect(surf, DREAM_PIG, (W.PIG_X, py, W.PIG_W, W.PIG_H))

    wash = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    wash.fill(DREAM_TINT)
    surf.blit(wash, (0, 0))


def draw_dream_label(surf, font, text="DREAM"):
    img = font.render(text, True, DREAM_LABEL)
    surf.blit(img, (8, surf.get_height() - img.get_height() - 6))


def _draw_debug(win, g, font, scale):
    def box(rect, color):
        x, y, w, h = rect
        pygame.draw.rect(win, color, (x * scale, y * scale, w * scale, h * scale), 2)

    box(g.pig_hitbox, HITBOX)
    for hz in g.hazards:
        box(hz.hitbox, HITBOX)
    for p in g.platforms:
        box((p.x_start, p.surface_y, p.x_end - p.x_start, 2), BAND)

    obs = g.observation()
    lines = [
        f"score {g.score}   step {g.steps}",
        f"dist   {obs[0]:+.3f}",
        f"height {obs[1]:+.3f}",
        f"vel    {obs[2]:+.3f}",
        f"ground {obs[3]:.0f}",
        f"speed  {obs[4]:+.3f}",
        f"hz lo/hi {obs[5]:+.3f}/{obs[6]:+.3f}",
        f"plat d/h {obs[7]:+.3f}/{obs[8]:+.3f}",
        f"plat hz lo/hi {obs[9]:+.3f}/{obs[10]:+.3f}",
    ]
    for i, line in enumerate(lines):
        img = font.render(line, True, TEXT, TEXT_BG)
        win.blit(img, (8, 8 + i * 18))


def render_rgb(g, anim=None, scroll=0.0):
    """Headless RGB frame (H, W, 3) for recording. No window required."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        # convert_alpha() (used when loading sprites) needs a display mode
        # to exist, even a 1x1 dummy one -- otherwise it raises once any
        # sprite file actually exists to be loaded.
        pygame.display.set_mode((1, 1))
    surf = pygame.Surface((W.NATIVE_W, W.NATIVE_H))
    draw_world(surf, g, anim or Animator(), scroll)
    draw_hud(surf, g)
    return np.transpose(pygame.surfarray.array3d(surf), (1, 0, 2))
