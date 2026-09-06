"""Watch or play the game.

    python play.py                  # play it yourself: SPACE to jump (hold for height)
    python play.py --mode expert    # scripted policy, a reference for "solved"
    python play.py --mode random    # random policy, the untrained baseline
    python play.py --mode expert --record run.gif --episodes 1

Keys: SPACE jump (hold for height) | D debug overlay | R reset | ESC quit
"""

import argparse
import random

import pygame

import game as G
import world as W
from game import ACTION_JUMP, ACTION_NOOP, PigRunner
from render import Animator, draw_hud, draw_world, _draw_debug

# Windows are in *seconds*, not pixels -- distance / current speed. Speed
# ramps up over an episode, so a fixed-pixel window quietly loses reaction
# time as the game speeds up. A pure "divide the old pixel window by current
# speed" conversion isn't quite enough either: hazard *width* is fixed in
# pixels, so how much time a hazard spends overlapping the pig shrinks as
# speed rises, while the jump's own arc duration doesn't change at all --
# the two don't scale together. These windows were swept directly at four
# points across the BASE_SPEED..MAX_SPEED range (200/250/300/340) and only
# kept if they worked at all four, so they're robust across the whole ramp,
# not just validated at one speed and assumed to generalize. Reused as-is
# for a hazard on a platform's deck too -- x-distance and height are all
# that matter to the timing, the elevation doesn't change any of it.
TAP_WINDOW = (0.05, 0.30)   # lower bound has margin beyond the bare minimum --
                            # a platform dismount is a real ~13-step fall, and
                            # a tight window can close one frame before landing
HOLD_WINDOW = (0.30, 0.50)   # later than TAP, not just narrower -- at the
                             # current pig/obstacle width, a held jump's
                             # window doesn't open until later relative to
                             # arrival than it used to; re-swept from scratch
                             # rather than assumed to shift by a fixed amount
PLATFORM_JUMP_WINDOW = (0.15, 0.50)  # re-swept after fixing the landing-position
                                     # bug -- the old (buggy) landing target was
                                     # more lenient, so the window that worked
                                     # against it no longer reliably lands now
                                     # that the bar for "counted as landed" is
                                     # the real one


def _end_episode(g, anim, reason, episodes, args, always_reset):
    """Log an episode's end and reset unless it's time to stop. Returns the
    updated episode count and whether the main loop should exit."""
    episodes += 1
    print(f"episode {episodes}: score {g.score} in {g.steps} steps ({reason})")
    stop = bool(args.episodes) and episodes >= args.episodes
    if not stop or always_reset:
        g.reset()
        anim.reset()
    return episodes, stop


def _wants_jump(hz, g):
    """Should we press jump right now to clear this hazard? Works the same
    whether hz is on the ground or on a platform's deck -- only x-distance
    and its own height matter, not absolute elevation."""
    if hz is None:
        return False
    t = (hz.x - W.PIG_X) / g.speed
    if hz.top_band > 60:  # needs a full hold
        return HOLD_WINDOW[0] <= t <= HOLD_WINDOW[1]
    return TAP_WINDOW[0] <= t <= TAP_WINDOW[1]


def _riding_platform(g, plat):
    """True only if the pig is actually standing on plat's deck -- not just
    grounded while plat's x-span happens to pass overhead. _active_platform()
    alone only checks x-coverage, so it doesn't distinguish the two."""
    return (
        plat is not None and g.on_ground
        and g.pig_y <= plat.surface_y - W.PIG_H + 1.0
    )


def expert_action(g):
    active = g._active_platform()

    # Actually on a platform's deck right now: the ground lane doesn't exist
    # from up here, so only the deck's own hazard (if any) matters.
    if _riding_platform(g, active):
        return ACTION_JUMP if _wants_jump(g.next_platform_hazard(), g) else ACTION_NOOP

    hz = g.next_hazard()
    plat = g._next_platform()

    # Consider jumping onto an upcoming platform. A held jump big enough to
    # reach the deck is also more than enough to clear whatever ground hazard
    # it spans (platforms only ever pair with a short bush), so there's no
    # conflict between "aim for the platform" and "clear what's beneath it."
    if plat is not None and plat.x_start > W.PIG_X and g.on_ground:
        t = (plat.x_start - W.PIG_X) / g.speed
        if PLATFORM_JUMP_WINDOW[0] <= t <= PLATFORM_JUMP_WINDOW[1]:
            return ACTION_JUMP
    if plat is not None and plat.covers(W.PIG_X) and not g.on_ground:
        return ACTION_JUMP  # keep rising onto the deck

    # No "and g.on_ground" gate here on purpose: sending JUMP while airborne
    # and still falling (not yet landed, e.g. dismounting a platform) is a
    # harmless no-op in the physics, but it means that if the window is
    # already open at the moment landing actually happens, the launch
    # fires on that exact frame -- instead of missing entirely because the
    # window had already closed by the time on_ground next became true.
    if _wants_jump(hz, g):
        return ACTION_JUMP
    if not g.on_ground and g.vy < 0:
        return ACTION_JUMP  # already committed to this jump -- keep holding
    return ACTION_NOOP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("human", "expert", "random"), default="human")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--scale", type=int, default=W.SCALE)
    ap.add_argument("--debug", action="store_true", help="start with the overlay on")
    ap.add_argument("--record", metavar="OUT.gif", help="also write the run to a gif")
    ap.add_argument("--episodes", type=int, default=0, help="stop after N deaths (0 = forever)")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_caption("Pig Runner v1")
    scale = args.scale
    win = pygame.display.set_mode((W.NATIVE_W * scale, W.NATIVE_H * scale))
    native = pygame.Surface((W.NATIVE_W, W.NATIVE_H))
    font = pygame.font.SysFont("menlo,monaco,consolas,monospace", 14)
    hud_font = pygame.font.SysFont("menlo,monaco,consolas,monospace", 16, bold=True)
    clock = pygame.time.Clock()

    g = PigRunner(args.seed)
    g.reset()
    anim = Animator()
    rng = random.Random(args.seed)
    debug = args.debug
    scroll = 0.0
    frames = []
    episodes = 0
    death_hold = 0
    running = True

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_d:
                    debug = not debug
                elif ev.key == pygame.K_r:
                    g.reset(); anim.reset(); death_hold = 0

        if not g.dead:
            if args.mode == "human":
                keys = pygame.key.get_pressed()
                action = ACTION_JUMP if keys[pygame.K_SPACE] else ACTION_NOOP
            elif args.mode == "expert":
                action = expert_action(g)
            else:
                action = rng.randint(0, G.NUM_ACTIONS - 1)
            g.step(action)
            scroll += g.speed * W.DT
            if g.steps >= 1000:          # mirrors r2dreamer's TimeLimit
                episodes, stop = _end_episode(g, anim, "time limit", episodes, args, always_reset=True)
                running = running and not stop
                continue
        else:
            death_hold += 1

        anim.update(g)
        draw_world(native, g, anim, scroll)
        draw_hud(native, g, hud_font)
        pygame.transform.scale(native, win.get_size(), win)
        if debug:
            _draw_debug(win, g, font, scale)
        pygame.display.flip()

        if args.record is not None:
            import numpy as np
            frames.append(np.transpose(pygame.surfarray.array3d(native), (1, 0, 2)).copy())

        if g.dead and death_hold > int(W.FPS * 0.8):
            episodes, stop = _end_episode(g, anim, "died", episodes, args, always_reset=False)
            running = running and not stop
            if not stop:
                death_hold = 0

        clock.tick(W.FPS)

    if args.record and frames:
        import imageio
        imageio.mimsave(args.record, frames, fps=W.FPS, loop=0)
        print(f"wrote {len(frames)} frames -> {args.record}")
    pygame.quit()


if __name__ == "__main__":
    main()
