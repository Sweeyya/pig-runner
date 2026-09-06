# Pig Runner

![demo](assets/demo.gif)

A Minecraft-flavored endless runner built as an RL environment. A pig
auto-runs right; sweet berry bushes, stacked blocks, a snow golem, and
elevated platforms come at it; jump, duck, or take the high road. Built to
train under [r2dreamer](https://github.com/NM512/r2dreamer) (DreamerV3), but
the interface is plain Gym-shaped enough to point any algorithm at it.

Not affiliated with or endorsed by Mojang — inspired by Minecraft, built with
entirely original art and code.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Sweeyya/pig-runner/blob/main/notebooks/train_and_watch.ipynb)

## Why this exists

The environment is deliberately small: 9 numbers in, 3 actions out, no
pixels anywhere near the agent. That's what makes training fast enough to
iterate on a laptop-class GPU (or Colab's free tier — see below). The design
choices are covered in more depth further down, but the short version: every
hazard exposes a continuous "what's coming and how high" signal instead of a
type label, so the agent has to read the situation, not memorize a pattern.

## Try it

```bash
git clone <this repo>
cd pig-runner
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python play.py                 # SPACE jump (hold for height), DOWN/S duck
.venv/bin/python play.py --mode expert   # what "solved" looks like
.venv/bin/python play.py --mode random   # the untrained baseline
```

`D` toggles a debug overlay (hitboxes + the live observation vector), `R`
resets, `ESC` quits.

## Toggle features in `config.py`

Every hazard is a flag. Flip one, run `play.py`, get a different game — no
other code changes needed:

```python
ENABLE_TALL_OBSTACLE = True   # needs a held jump, not a tap
ENABLE_SNOW_GOLEM     = True   # forces a jump-or-duck read
ENABLE_PLATFORMS      = True   # alternate route: jump up and over instead
ENABLE_SPEED_RAMP     = True   # pace picks up over the episode
```

All four off reproduces the original minimal version exactly: one hazard
(the bush), two actions, fixed speed.

## The game

| | |
|---|---|
| Actions | `0` nothing, `1` jump (hold for height), `2` duck |
| Hazards | bush (tap-jump), 2-block stack (held jump), snow golem shot (jump low ones, duck high ones), platform (alternate route over a bush) |
| Observation | 9 floats, **never pixels** — see below |
| Reward | +1 per hazard cleared, 0 otherwise, 0 on death |
| Episode ends | on death; capped at 1000 steps (~20s at 50 steps/s) |
| Speed | ramps from 200 to 340 px/s over the episode |

Baselines with everything on: random policy scores **0-3** and dies within
the first few hundred steps; a scripted policy that reads each hazard's
height correctly scores **16-19** and survives the full cap. That gap is the
learning signal.

## Observation

| # | Value | Notes |
|---|---|---|
| 0 | distance to next hazard | fraction of screen width |
| 1 | pig height above ground | 0 when grounded |
| 2 | vertical velocity | positive is up |
| 3 | on ground | 0 or 1 (true whether on real ground or a platform) |
| 4 | current speed | normalized 0 (start) to 1 (ramp cap) — without this, "distance" alone would mean a different amount of reaction time depending on speed |
| 5, 6 | next hazard's bottom/top band | the height range it occupies above ground — this is what makes jump-vs-duck a numeric decision, not a hidden type label |
| 7, 8 | next platform's distance/height | clipped far/0 if none is coming |

Jumping is variable-height: press to launch, hold to keep rising, release to
cut the arc short. Ducking has no physics of its own — it's a hitbox change
that only lasts as long as the action is held, so it has to stay pressed for
a hazard's entire pass, unlike jump which carries through on its own once
launched.

## Files

| File | |
|---|---|
| `world.py` | shared constants (canvas size, ground line, pig geometry) |
| `game.py` | pure game logic — no pygame, no gym, no RL deps |
| `hazards.py` | each hazard type + the weighted spawn registry `config.py` drives |
| `config.py` | the toggles and tunables described above |
| `env.py` | r2dreamer-compatible wrapper |
| `render.py` | pygame renderer, rectangles now, sprites when you draw them |
| `play.py` | play it yourself / watch a policy / record a gif |
| `assets/README.md` | the art spec to draw against |
| `integration/` | drop-in config and code for r2dreamer |
| `notebooks/` | Colab notebook: train on a free GPU, watch results inline |

## Wiring into r2dreamer

The interface matches r2dreamer's own envs (old-gym signatures, dict obs
carrying `is_first`/`is_last`/`is_terminal`), so no adapter is needed.

1. Copy the logic files into r2dreamer:
   ```bash
   cp world.py game.py hazards.py config.py <r2dreamer>/envs/
   cp env.py <r2dreamer>/envs/pigrunner.py
   ```
2. Copy `integration/pigrunner.yaml` to `<r2dreamer>/configs/env/pigrunner.yaml`.
3. Add the branch in `integration/make_env_branch.py` to `make_env()` in
   `<r2dreamer>/envs/__init__.py`.
4. Train:
   ```bash
   python train.py env=pigrunner
   ```

Two things worth knowing about that wiring:

- **The 1000-step cap is not implemented here.** r2dreamer's `wrappers.TimeLimit`
  owns it via `time_limit: 1000`. This env only reports real death, by setting
  `info["discount"] = 0.0`. That keeps death a *termination* (future worth zero)
  and the step cap a *truncation* (future still worth something) — collapsing
  the two would teach the agent that surviving is as bad as dying.
- **`render.py` is never imported during training.** r2dreamer runs `env_num`
  copies in subprocesses, and 16 of them opening windows would be a mess.
  Rendering is opt-in, via `play.py` or `env.render()`.

## No local GPU? Use Colab

DreamerV3 trains a world model, which benefits meaningfully from a GPU even
on an observation this small. `notebooks/train_and_watch.ipynb` clones the
repo, installs everything, trains on Colab's free-tier GPU, then renders a
rollout to a GIF and displays it inline — no terminal, no window, nothing
local required. Recommended for anyone trying this out, not just people
without a GPU: it's the zero-setup path.

## Not in this version, by design

Mining through blocks and placing blocks to bridge gaps — the original v0
scope deliberately started smaller than this and grew from there; those two
remain a natural next step. Day/night was considered and left out; it
wouldn't change the observation or the decision-making, just the palette.
Flight was considered and cut entirely: with no cost it would dominate every
other action, so the agent would just fly the whole episode and learn
nothing.
