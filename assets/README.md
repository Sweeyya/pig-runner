# Art spec

Everything below is what the renderer already looks for. Drop matching PNGs in
this folder and they are used automatically — no code changes. Anything missing
falls back to the colored rectangles, so you can add art one frame at a time.

## Canvas

- Native canvas **640x360**, scaled x3 to a 1920x1080 window.
- Tile size **64x64**. Ground surface sits at y=300.
- Transparent PNG, no padding, one file per frame.

Hazard/pig sizes are 4x the original v0/v1 numbers (they went through two
doublings: once for sprite detail, once more because the first pass still
looked too small/pixelated on screen — the ceiling on visible detail is the
*final on-screen pixel size*, not the source art resolution, so there was no
way around growing the world-space size itself). Gameplay timing is
unchanged throughout -- see game.py's own notes on that.

The dirt/grass band below the ground line is deliberately kept thin (one
tile) regardless of how large everything else gets -- it's pure decoration
with no gameplay function, so it doesn't get to compete for screen space the
way the sky's jump-clearance requirement does.

Art is authored bigger than these numbers (see `tools/build_sprites.py`) --
the renderer fits it down at draw time and caches the result, so keep source
files high-resolution rather than pre-shrinking them.

## Files

| File | Size | Notes |
|---|---|---|
| `pig_run_00..03.png` | 64x64 | 4-frame run cycle, plays at 12fps |
| `pig_rise_00.png` | 64x64 | rising (vy < 0) |
| `pig_fall_00.png` | 64x64 | falling (vy > 0) |
| `pig_land_00.png` | 64x64 | landing squash, shows for 4 steps |
| `pig_duck_00.png` | 64x32 | crouched, feet planted, drawn at ground level |
| `pig_death_00..03.png` | 64x64 | plays once at 10fps |
| `bush_00.png` | 64x48 | sweet berry bush |
| `tall_obstacle_00.png` | 32x88 | 2-3 block stack; needs a held jump, not a tap. Narrower than you'd guess from a straight 4x scale -- combined with the bigger pig, a wider obstacle became mathematically uncrossable at the game's slowest speed (see hazards.py) |
| `snowball_low_00.png` | ~40x56 | grounded shot — jump clears it, like the bush |
| `snowball_high_00.png` | ~40x160 | floating shot — tall by necessity, since no jump reaches it; duck is the only way under. Feel free to draw it as a flurry/icicle rather than a literal ball, so the height doesn't read as strange |
| *(decorative, optional)* | — | a small golem figure near the right edge of the frame when a snowball spawns is a nice flourish — it isn't a separate collidable object, so it can be baked into the snowball sprite's background or skipped entirely |
| platform deck | any width | drawn procedurally right now (a plank strip); a tileable wood-plank texture can replace it later without a code change |

Reserved so v2 art slots in without renumbering: `pig_mine_00..03.png`,
`pig_place_00..02.png`.

The pig always faces right and is drawn at x=96. Bush and pig art currently
in the repo were generated from hand-drawn source art via
`tools/build_sprites.py` (trim → squash/stretch → downscale) — see that file
if you draw more poses and want to regenerate.

## Palette

Sky `#87BAE3` - cloud `#DEEEF7` - grass `#6AAA4B` / edge `#568C3D` - dirt `#866043` / dark `#6E4E37` - pig `#F1A7B2` / dark `#CE818E` / snout `#E08998` - bush `#3A6E2F` / dark `#285223` - berry `#BF362E` - stone `#96969B` / dark `#6E6E74` - snow `#F0F6FA` / shade `#C8D7E1` - platform `#A88056` / side `#805C3C`
