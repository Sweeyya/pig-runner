"""Hazard types and the spawn registry. Each hazard is a small self-contained
class; toggling one off in config.py just removes it from the weighted
choices below -- nothing else needs to change.

Every hazard exposes:
  .x, .w              -- world position and width (scrolls via .update(dx))
  .hitbox             -- (x, y, w, h) collision rect, inset from the art
  .bottom_band/.top_band -- height above ITS OWN surface the hazard occupies
                            (px), 0 = touches that surface. This is what the
                            agent observes -- a continuous "what's coming"
                            signal, not a type label -- so how high to jump
                            is a numeric decision, never a hidden one.
  .surface_y/.on_platform -- a hazard normally sits on the real ground
                            (surface_y=GROUND_Y), but the exact same class
                            can be planted on a platform's deck instead
                            (surface_y=that platform's surface) -- nothing
                            about collision or rendering needs to know the
                            difference, since both just read from surface_y.

Platforms are terrain, not hazards: they're never checked for collision
themselves (see game.py's landing logic) and only ever pair with a
ground-level Bush, positioned well above tap-jump-clearing height for one,
so there is always a real ground route underneath. A platform's own deck
may separately carry a hazard (a second, independent Bush instance with
surface_y set to that platform's surface) -- that hazard lives in the same
hazards list as everything else, not on the Platform object.
"""

try:  # works both standalone and when copied into r2dreamer's envs/ package
    from . import config as C
    from . import world as W
except ImportError:
    import config as C
    import world as W

# --- Geometry ---------------------------------------------------------------
# Every number here is 4x the original v0/v1 tuning, matching world.py and
# game.py's 4x scale-up -- same relative clearances, just more sprite detail.
BUSH_W, BUSH_H = 64, 48                  # the fixed jump clears this with room to spare

PLATFORM_THICKNESS = 24
# NOT scaled with everything else on purpose: how wide a platform needs to be
# depends on (time spent above PLATFORM_HEIGHT during a jump) x (speed), and
# neither of those changed in this pass -- jump timing is scale-invariant by
# construction, and speed is a separate, unscaled pace knob.
PLATFORM_MARGIN = 80.0                    # covers the ~143px above-height scroll at MAX_SPEED, with margin

# A platform that will carry its own deck hazard is built wider from the
# start, rather than trying to fit one into a normal-width platform -- the
# two needs (enough room to land at all, enough room to *also* clear a
# hazard once landed) don't fit the same margin. Whether a platform gets a
# deck hazard is decided once, at spawn time, and the width follows from
# that decision -- not two independent rolls that could conflict.
PLATFORM_MARGIN_WITH_HAZARD = 220.0

# Leading vs trailing clearance for a deck-mounted hazard, deliberately
# asymmetric: a jump aimed at the deck is still passing through low, unsafe
# heights on the way in -- and *where* along the deck it finally lands
# varies with exactly when the jump was triggered within its own window --
# so a hazard too close to the leading edge risks getting clipped before
# landing completes, or landed on top of outright. Verified against the
# real game loop (not just an isolated single-platform scenario), since
# real timing variance turned out to matter more than the isolated case
# suggested. The trailing edge has no such constraint -- once past the
# hazard the pig just coasts to the far end -- so it stays small.
PLATFORM_HAZARD_LEADING_MARGIN = 180.0
PLATFORM_HAZARD_TRAILING_MARGIN = 30.0

# Hitbox insets so near-misses read as near-misses, not stolen deaths.
BOX_INSET_X, BOX_INSET_TOP = 12, 8        # shared by every box hazard


class Hazard:
    kind = "hazard"
    inset_x, inset_top = BOX_INSET_X, BOX_INSET_TOP

    def __init__(self, x, surface_y=None):
        self.x = x
        self.passed = False
        self.on_platform = surface_y is not None
        self.surface_y = surface_y if surface_y is not None else W.GROUND_Y

    def update(self, dx):
        self.x -= dx

    @property
    def right(self):
        return self.x + self.w

    @property
    def hitbox(self):
        """Default shape for a box sitting on its surface, inset from the art."""
        return (
            self.x + self.inset_x,
            self.surface_y - self.h + self.inset_top,
            self.w - 2 * self.inset_x,
            self.h - self.inset_top,
        )


class Bush(Hazard):
    kind = "bush"
    w, h = BUSH_W, BUSH_H
    bottom_band, top_band = 0.0, float(BUSH_H)


class Platform:
    """Terrain, not a hazard -- never collided with directly. Spans a Bush,
    floating well above tap-jump height, so the ground route always exists.

    May be built with a hazard already standing on its own deck --
    `deck_hazard` is only a one-shot handoff for game.py to append into the
    normal hazards list at spawn time; the Platform itself doesn't track it
    afterward.
    """

    kind = "platform"

    def __init__(self, x_start, x_end, height):
        self.x_start = x_start
        self.x_end = x_end
        self.height = height       # px above ground the walkable surface sits
        self.deck_hazard = None

    def update(self, dx):
        self.x_start -= dx
        self.x_end -= dx

    def covers(self, x):
        return self.x_start <= x <= self.x_end

    @property
    def right(self):
        return self.x_end

    @property
    def surface_y(self):
        return W.GROUND_Y - self.height


_TYPES = {
    "bush": Bush,
}


def _enabled_weights():
    return {"bush": C.SPAWN_WEIGHTS.get("bush", 1)}


def _pick_kind(rng, weights):
    kinds = list(weights)
    picks = [weights[k] for k in kinds]
    return rng.choices(kinds, weights=picks, k=1)[0]


def plan_next(rng):
    """Decide what the next spawn will be, without committing to a screen
    position yet. Split out from materialize() so game.py can see, before it
    sizes the gap leading up to this spawn, whether a platform (and
    especially a deck hazard) is coming -- both cost real extra time
    (an early decision point, a dismount fall) that a gap sized only from
    hazard-to-hazard pixel distance doesn't know to leave room for."""
    weights = _enabled_weights()
    kind = _pick_kind(rng, weights)
    wants_platform = C.ENABLE_PLATFORMS and kind == "bush" and rng.random() < C.PLATFORM_CHANCE
    deck_kind = None
    if wants_platform and rng.random() < C.PLATFORM_HAZARD_CHANCE:
        deck_kind = _pick_kind(rng, weights)
    return {"kind": kind, "wants_platform": wants_platform, "deck_kind": deck_kind}


def materialize(plan, x, rng):
    """Build the actual Hazard/Platform objects for a plan from plan_next(),
    positioned at x. Returns (hazard, platform_or_None); a returned platform
    may carry its own deck hazard as `platform.deck_hazard` (None if not) --
    game.py reads that once and appends it to the same hazards list as
    everything else."""
    hazard = _TYPES[plan["kind"]](x)

    platform = None
    if plan["wants_platform"]:
        margin = PLATFORM_MARGIN_WITH_HAZARD if plan["deck_kind"] else PLATFORM_MARGIN
        platform = Platform(
            x_start=x - margin,
            x_end=x + BUSH_W + margin,
            height=C.PLATFORM_HEIGHT,
        )
        if plan["deck_kind"] is not None:
            deck_cls = _TYPES[plan["deck_kind"]]
            lo = platform.x_start + PLATFORM_HAZARD_LEADING_MARGIN
            hi = platform.x_end - PLATFORM_HAZARD_TRAILING_MARGIN - deck_cls.w
            if hi > lo:
                platform.deck_hazard = deck_cls(rng.uniform(lo, hi), surface_y=platform.surface_y)
    return hazard, platform


# Extra gap-before-spawn, added on top of the normal MIN/MAX_GAP_SEC roll,
# to cover costs a plain hazard-to-hazard pixel gap doesn't know about:
#
# - A deck-hazard platform's own decision point (where the expert must
#   commit to jumping onto it) sits PLATFORM_MARGIN_WITH_HAZARD px *before*
#   its paired bush -- added directly in px below, since that margin is
#   itself already a spatial (not time) quantity.
# - Dismounting any platform is a real freefall (from PLATFORM_HEIGHT, at
#   GRAVITY) before the ground becomes reactable again -- 120px works out to
#   ~0.26s; PLATFORM_EXIT_LEAD_SEC adds buffer on top of that so the *next*
#   hazard after a platform still gets a fair reaction window.
PLATFORM_EXIT_LEAD_SEC = 0.35


def extra_gap_px(plan, prev_was_platform, speed):
    px = 0.0
    if prev_was_platform:
        px += PLATFORM_EXIT_LEAD_SEC * speed
    if plan["deck_kind"] is not None:
        px += PLATFORM_MARGIN_WITH_HAZARD
    return px
