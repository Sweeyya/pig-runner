"""One-off pipeline: turns hand-drawn source art (large, painterly) into the
PNGs in assets/. Output is deliberately bigger than the game's own pixel
boxes (4x) -- render.py fits it down live and caches the result, so this
preserves far more of the original linework/shading than pre-shrinking to
the exact tiny size ever could. Not part of the game itself -- run once
whenever new source art needs processing.

    .venv/bin/python tools/build_sprites.py

Techniques used, not a general-purpose image library:
  - trim(): crop to the alpha bounding box, so downstream scaling isn't
    fighting a huge transparent margin.
  - place(): scale trimmed content into a fixed output canvas with an
    independent x/y squash-stretch factor, anchored so feet stay planted on
    the bottom edge -- the game positions sprites assuming that.
  - tint_toward(): blend colored (non-outline) pixels toward a target color,
    preserving black linework and alpha, for the death-frame "hurt" look.
"""

import os

import numpy as np
import pygame

pygame.init()
import os as _os
_os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame.display.set_mode((1, 1))

SRC = "/Users/sweeya/Downloads"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def load_rgba(path):
    surf = pygame.image.load(path)
    return surf.convert_alpha()


def load_gif_frame(path, index):
    import imageio.v2 as imageio
    frames = imageio.mimread(path)
    f = frames[index]
    mode = "RGBA" if f.shape[-1] == 4 else "RGB"
    surf = pygame.image.frombuffer(np.ascontiguousarray(f).tobytes(), (f.shape[1], f.shape[0]), mode)
    return surf.convert_alpha()


def trim(surf):
    alpha = pygame.surfarray.array_alpha(surf)  # (W, H)
    cols = np.any(alpha > 8, axis=1)
    rows = np.any(alpha > 8, axis=0)
    x0, x1 = np.argmax(cols), len(cols) - 1 - np.argmax(cols[::-1])
    y0, y1 = np.argmax(rows), len(rows) - 1 - np.argmax(rows[::-1])
    return surf.subsurface((x0, y0, x1 - x0 + 1, y1 - y0 + 1)).copy()


def place(trimmed, canvas_w, canvas_h, sx=1.0, sy=1.0):
    """Scale trimmed content to fit (canvas_w, canvas_h) preserving aspect,
    then stretch by (sx, sy) on top, clamped to still fit. Feet-on-ground:
    anchored bottom-center, since that's what the game assumes."""
    tw, th = trimmed.get_size()
    base = min(canvas_w / tw, canvas_h / th)
    scale_x = min(base * sx, canvas_w / tw)
    scale_y = min(base * sy, canvas_h / th)
    w, h = max(1, round(tw * scale_x)), max(1, round(th * scale_y))
    scaled = pygame.transform.smoothscale(trimmed, (w, h))
    canvas = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
    canvas.blit(scaled, ((canvas_w - w) // 2, canvas_h - h))
    return canvas


def tint_toward(surf, target, amount, outline_cutoff=60):
    """Blend colored pixels toward `target` RGB by `amount` (0-1). Pixels
    near-black (outline strokes) are left alone so linework stays crisp."""
    view = pygame.surfarray.pixels3d(surf)       # a view into the surface
    rgb = view.astype(np.float32)                # a separate copy, for the math
    is_outline = rgb.max(axis=2) < outline_cutoff
    blended = rgb * (1 - amount) + np.array(target, dtype=np.float32) * amount
    view[~is_outline] = blended[~is_outline].astype(np.uint8)  # write back into the view
    del view
    return surf


def fade(surf, factor):
    a = pygame.surfarray.pixels_alpha(surf)
    a[:] = (a.astype(np.float32) * factor).astype(np.uint8)
    return surf


def save(surf, name):
    pygame.image.save(surf, os.path.join(OUT, name + ".png"))
    print("wrote", name)


def split_bands(surf, horizon_frac):
    """Split a combined sky+ground image into two bands at horizon_frac (0-1
    down the image). Each band is later stretched independently to fill its
    own native-canvas region, so the art's horizon lands exactly on GROUND_Y
    regardless of the source image's own proportions."""
    w, h = surf.get_size()
    split = round(h * horizon_frac)
    sky = surf.subsurface((0, 0, w, split)).copy()
    ground = surf.subsurface((0, split, w, h - split)).copy()
    return sky, ground


def cut_blocks(surf, spans, row):
    """Crop fixed-size block tiles out of a sprite sheet. `spans` are
    (x0, x1) inclusive pixel columns per block; `row` is the (y0, y1)
    inclusive rows all blocks share."""
    y0, y1 = row
    out = []
    for x0, x1 in spans:
        out.append(surf.subsurface((x0, y0, x1 - x0 + 1, y1 - y0 + 1)).copy())
    return out


def main():
    still = trim(load_rgba(f"{SRC}/Piggy-still.png"))
    run = trim(load_gif_frame(f"{SRC}/Piggy-run.gif", 1))
    bush = trim(load_rgba(f"{SRC}/bush.png"))

    save(place(bush, 256, 192), "bush_00")

    # Run cycle: alternate the two drawn poses, exaggerating each with
    # squash/stretch so the pair reads as a bounce, not just two stills.
    save(place(still, 256, 256, 1.00, 1.00), "pig_run_00")   # neutral / passing
    save(place(run, 256, 256, 0.90, 1.15), "pig_run_01")     # stretched -- up
    save(place(still, 256, 256, 1.00, 1.00), "pig_run_02")   # neutral / passing
    save(place(run, 256, 256, 1.12, 0.88), "pig_run_03")     # squashed -- down

    save(place(still, 256, 256, 0.88, 1.22), "pig_rise_00")  # stretched tall
    save(place(run, 256, 256, 1.05, 0.95), "pig_fall_00")    # slight squash, trailing legs
    save(place(still, 256, 256, 1.30, 0.75), "pig_land_00")  # dramatic squash

    # Death: same base pose, increasingly red and increasingly faded/squashed
    # -- reads as "hurt" then "poofing away" across the 4 frames.
    steps = [
        (0.40, 1.00, 1.00, 1.00),
        (0.70, 1.00, 0.95, 0.97),
        (0.90, 1.00, 0.85, 0.85),
        (1.00, 1.00, 0.70, 0.65),
    ]
    for i, (redness, alpha_factor, sx, sy) in enumerate(steps):
        frame = place(still, 256, 256, sx, sy)
        tint_toward(frame, (225, 25, 25), redness)
        fade(frame, alpha_factor)
        save(frame, f"pig_death_{i:02d}")

    # Background: sky above the horizon, snow-capped ground below it. Split
    # at the horizon (measured directly off the source art -- it isn't at a
    # round fraction) so each band can be stretched independently to fill
    # its own native-canvas region without shifting where the ground line
    # actually falls. Bands are the full NATIVE_W wide since neither one
    # scrolls -- this is a static backdrop, not a tiled/scrolling texture.
    bg = load_rgba(f"{SRC}/backgroun-and-ground.png")
    sky_band, ground_band = split_bands(bg, horizon_frac=0.768)
    save(pygame.transform.smoothscale(sky_band, (2560, 1200)), "bg_sky")     # 4x of 640x300 (GROUND_Y)
    save(pygame.transform.smoothscale(ground_band, (2560, 240)), "bg_ground")  # 4x of 640x60 (NATIVE_H - GROUND_Y)

    # Platform blocks: a 5-block sheet. Block 2 (0-indexed: 1) is a left
    # edge cap, block 4 (index 3) a right edge cap -- both have a closed
    # border on the outward side so they read as a clean end, not a cut-off
    # tile. Blocks 1, 3, 5 (indices 0, 2, 4) are open on both sides and
    # become the randomized middle fill, so a long platform doesn't look
    # like the same tile stamped repeatedly.
    sky_blocks = load_rgba(f"{SRC}/sky-block.png")
    spans = [(211, 590), (656, 1037), (1102, 1483), (1541, 1926), (1994, 2359)]
    blocks = cut_blocks(sky_blocks, spans, row=(1255, 1639))
    save(pygame.transform.smoothscale(blocks[1], (256, 256)), "platform_left")
    save(pygame.transform.smoothscale(blocks[3], (256, 256)), "platform_right")
    for out_i, block_i in enumerate((0, 2, 4)):
        save(pygame.transform.smoothscale(blocks[block_i], (256, 256)), f"platform_mid_{out_i:02d}")


if __name__ == "__main__":
    main()
