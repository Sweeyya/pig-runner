"""Watch or play the game.

    python play.py                  # play it yourself: SPACE jump, DOWN/S duck
    python play.py --mode expert    # scripted policy, a reference for "solved"
    python play.py --mode random    # random policy, the untrained baseline
    python play.py --mode expert --record run.gif --episodes 1

Keys: SPACE jump (hold for height) | DOWN/S duck | D debug overlay | R reset | ESC quit
"""

import argparse
import random

import pygame

import game as G
import world as W
from game import ACTION_DUCK, ACTION_JUMP, ACTION_NOOP, PigRunner
from render import Animator, draw_hud, draw_world, _draw_debug

# Empirically robust thresholds (px) for the scripted expert -- see the
# jump-clearance tuning notes in game.py: tap apex ~29px, held apex ~47px.
TAP_WINDOW = (16, 40)
HOLD_WINDOW = (16, 70)
DUCK_WINDOW = (-20, 30)  # duck has no physics carry-through like jump does --
                         # must stay held for the hazard's full x-overlap
PLATFORM_JUMP_WINDOW = (30, 90)


def expert_action(g):
    hz = g.next_hazard()
    plat = g._next_platform()

    if plat is not None and plat.x_start > W.PIG_X and g.on_ground:
        d = plat.x_start - W.PIG_X
        if PLATFORM_JUMP_WINDOW[0] <= d <= PLATFORM_JUMP_WINDOW[1]:
            return ACTION_JUMP
    if plat is not None and plat.covers(W.PIG_X) and not g.on_ground:
        return ACTION_JUMP  # keep rising onto the deck

    if hz is None:
        return ACTION_NOOP
    d = hz.x - W.PIG_X

    if hz.bottom_band > 0:  # floating -- duck under it
        if DUCK_WINDOW[0] <= d <= DUCK_WINDOW[1]:
            return ACTION_DUCK
        return ACTION_NOOP

    if hz.top_band > 30:  # needs a full hold
        if HOLD_WINDOW[0] <= d <= HOLD_WINDOW[1] and g.on_ground:
            return ACTION_JUMP
    else:
        if TAP_WINDOW[0] <= d <= TAP_WINDOW[1] and g.on_ground:
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
                if keys[pygame.K_SPACE]:
                    action = ACTION_JUMP
                elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    action = ACTION_DUCK
                else:
                    action = ACTION_NOOP
            elif args.mode == "expert":
                action = expert_action(g)
            else:
                action = rng.randint(0, G.NUM_ACTIONS - 1)
            g.step(action)
            scroll += g.speed * W.DT
            if g.steps >= 1000:          # mirrors r2dreamer's TimeLimit
                episodes += 1
                print(f"episode {episodes}: score {g.score} in {g.steps} steps (time limit)")
                if args.episodes and episodes >= args.episodes:
                    running = False
                g.reset(); anim.reset()
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
            episodes += 1
            print(f"episode {episodes}: score {g.score} in {g.steps} steps (died)")
            if args.episodes and episodes >= args.episodes:
                running = False
            else:
                g.reset(); anim.reset(); death_hold = 0

        clock.tick(W.FPS)

    if args.record and frames:
        import imageio
        imageio.mimsave(args.record, frames, fps=W.FPS, loop=0)
        print(f"wrote {len(frames)} frames -> {args.record}")
    pygame.quit()


if __name__ == "__main__":
    main()
