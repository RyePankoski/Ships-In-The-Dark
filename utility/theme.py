"""The look of the game in one place: palette, font, and CRT post-processing settings.

Colour rules (one meaning per colour):
    AMBER  - the console itself: frames, labels, headings, inactive-but-present.
             Bright amber doubles as "caution" (recharging, tracking, hull getting low).
    GREEN  - live data: sensor returns, radar, scans, readouts, your laser.
    RED    - threats only: locks on you, damage, hostile fire, things that kill you.
    WHITE  - you: your own marker, hot cores of beams and blips, your FTL/blink effects.

If you want to reskin the game, change the values here and nothing else.
"""
import os
import random
import sys
from pathlib import Path

import pygame

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BLACK = (0, 0, 0)
BG = (3, 8, 5)                  # panel fill
BG_SENSOR = (4, 10, 6)          # inside instrument screens

AMBER = (210, 150, 0)
AMBER_BRIGHT = (255, 200, 40)
AMBER_DIM = (90, 65, 0)
AMBER_FAINT = (45, 32, 0)

GREEN = (70, 235, 110)
GREEN_BRIGHT = (175, 255, 190)
GREEN_DIM = (30, 110, 55)
GREEN_FAINT = (10, 32, 16)

RED = (255, 60, 50)
RED_BRIGHT = (255, 120, 110)
RED_DIM = (120, 28, 22)

WHITE = (235, 240, 230)
GREY = (120, 120, 105)          # "nothing here" / idle text

# World-view things that aren't UI
ASTEROID = (120, 90, 45)

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
FONT_FILE = "ShareTechMono-Regular.ttf"


def _asset_dir():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


_font_cache = {}


class _TextFlicker:
    """Every so often one piece of on-screen text stutters, like a failing phosphor.

    Only one string flickers at a time. Once the next flicker is due, each string
    rendered has a small chance of being the one picked, so it lands on random
    labels rather than whatever gets drawn first each frame.
    """

    def __init__(self):
        self.text = None
        self.until = 0
        self.next_at = 0

    def factor(self, text):
        """0-255 brightness to draw `text` at right now (255 = untouched)."""
        if TEXT_FLICKER_INTERVAL[1] <= 0 or not text.strip():
            return 255
        now = pygame.time.get_ticks()
        if self.text is not None:
            if now >= self.until:
                self.text = None
                self.next_at = now + int(random.uniform(*TEXT_FLICKER_INTERVAL) * 1000)
            elif text == self.text:
                # Stutter: mostly off or dim, with brief full-strength pops
                return random.choice((0, 0, 40, 90, 255))
            return 255
        if self.next_at == 0:
            self.next_at = now + int(random.uniform(*TEXT_FLICKER_INTERVAL) * 1000)
        elif now >= self.next_at and random.random() < 0.05:
            self.text = text
            self.until = now + random.randint(*TEXT_FLICKER_DURATION_MS)
            return 0
        return 255


_flicker = _TextFlicker()


class _Font(pygame.font.Font):
    def render(self, text, antialias, color, background=None):
        surf = super().render(text, antialias, color, background)
        k = _flicker.factor(text)
        if k < 255:
            surf.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
        return surf

    def render_steady(self, text, antialias, color, background=None):
        """Render without any chance of flicker (for things baked once and kept)."""
        return super().render(text, antialias, color, background)


def font(size):
    """The game's one font at a given pixel size. Cached, so it's fine to call every frame."""
    size = max(6, int(round(size)))
    f = _font_cache.get(size)
    if f is None:
        path = os.path.join(_asset_dir(), "fonts", FONT_FILE)
        try:
            f = _Font(path, size)
        except (FileNotFoundError, OSError):
            f = _Font(None, size)
        _font_cache[size] = f
    return f


def legacy_font(size):
    """Same footprint as the old pygame.font.Font(None, size) calls, so layouts don't shift."""
    return font(size * 0.68)


# ---------------------------------------------------------------------------
# CRT post-processing (see asset_handlers/crt.py)
# ---------------------------------------------------------------------------
CRT_ENABLED = True
CRT_TOGGLE_KEY = pygame.K_F9

GLOW_STRENGTH = 110             # 0-255: how much of the blurred image is added back
GLOW_DOWNSCALE = 6              # bigger = wider, softer glow (and cheaper)

SCANLINE_SPACING = 3
SCANLINE_ALPHA = 70             # 0-255
VIGNETTE_ALPHA = 110            # darkness at the very corners

# Grunge (see asset_handlers/grime.py and crt.py). Set any number to 0 to turn that effect off.
GRIME_ENABLED = True            # stained, scratched, burnt-in panel textures
GRAIN_STRENGTH = 14             # 0-255: brightest speckle of the animated static
HUM_BAR_STRENGTH = 9            # 0-255: the slow bright band that rolls down the tube
HUM_BAR_SPEED = 0.06            # pixels per millisecond
TEAR_CHANCE = 0.02              # per frame: a strip of the picture jumps sideways
GLASS_DIRT = 1.0                # dust, smudges and scratches on the tube glass (0 = clean)
FLICKER_CHANCE = 0.01           # per frame: whole picture dims for a frame
READOUT_SPEED = 0.5             # background terminals in the top panel: 1.0 = original pace, lower = slower
TEXT_FLICKER_INTERVAL = (4.0, 11.0)    # seconds between one label stuttering (0, 0 = never)
TEXT_FLICKER_DURATION_MS = (150, 450)  # how long the stutter lasts
