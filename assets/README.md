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
| `pig_death_00..03.png` | 64x64 | plays once at 10fps |
| `bush_00.png` | 64x48 | sweet berry bush — same file whether it's spawned on the ground or on a platform's deck, since it's the same class either way |
| `snow_golem_00.png` | 32x88 | 2-block stack (body + head); needs the jump's peak actually over it, tighter timing than the bush. Narrower than you'd guess from a straight 4x scale -- combined with the bigger pig, a wider obstacle became mathematically uncrossable at the game's slowest speed (see hazards.py). Also shared between ground and deck spawns |
| `bg_sky.png` | 2560x1200 | static sky band, above the horizon. Stretched to fill the canvas from y=0 to GROUND_Y — doesn't scroll |
| `bg_ground.png` | 2560x240 | static ground band, below the horizon. Stretched to fill GROUND_Y to the canvas bottom — doesn't scroll either; the horizon lines up with GROUND_Y exactly because each band is scaled to its own region independently, regardless of the source art's own proportions |
| `platform_left.png` / `platform_right.png` | 256x256 | end caps for a platform's deck — closed border on the outward side so the platform reads as a clean edge, not a cut-off tile |
| `platform_mid_00..02.png` | 256x256 | middle-fill tiles, randomized per slot (seeded off the platform itself, so it's stable frame to frame) so a long platform doesn't look like one tile stamped repeatedly |

Platform art draws a full tile (64x64) tall now, not the old thin decorative
strip -- it reads as an actual floating block instead of a thin deck. This
is render-only: `PLATFORM_THICKNESS` (the old strip height) still exists
for the no-sprite fallback and has no effect on collision either way.

Reserved so v2 art slots in without renumbering: `pig_mine_00..03.png`,
`pig_place_00..02.png`.

The pig always faces right and is drawn at x=96. All art currently in the
repo was generated from hand-drawn source art via `tools/build_sprites.py`
(trim/split/cut → squash-stretch or scale → downscale) — see that file if
you draw more poses or blocks and want to regenerate.

Not yet drawn: a falling-snow (or similar) particle layer over the flat
sky, replacing the old procedural clouds -- clouds still draw in the
no-sprite fallback (`_draw_clouds` in render.py) but never appear once
`bg_sky.png` exists, since the two looks don't mix.

## Palette

Sky/ground now come from `bg_sky.png`/`bg_ground.png` art rather than flat
fill colors, so the swatches below only describe the procedural fallback
and the hazards/pig, which are still colored rects:

Sky `#87BAE3` - cloud `#DEEEF7` - grass `#6AAA4B` / edge `#568C3D` - dirt `#866043` / dark `#6E4E37` - pig `#F1A7B2` / dark `#CE818E` / snout `#E08998` - bush `#3A6E2F` / dark `#285223` - berry `#BF362E` - snow `#F0F6FA` / shade `#C8D7E1` - golem nose `#DB8228` - platform (fallback only): same grass/dirt tones as the ground
