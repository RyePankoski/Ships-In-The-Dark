"""The game's one font, and the stutter that makes its text flicker.

Sizes and the flicker timing are set in utility/theme.py.
"""
import os
import random

import pygame

from utility.paths import asset_dir
from utility.theme import FONT_FILE, FONT_SCALE, TEXT_FLICKER_DURATION_MS, TEXT_FLICKER_INTERVAL


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
    size = max(6, int(round(size * FONT_SCALE)))
    f = _font_cache.get(size)
    if f is None:
        path = os.path.join(asset_dir(), "fonts", FONT_FILE)
        try:
            f = _Font(path, size)
        except (FileNotFoundError, OSError):
            f = _Font(None, size)
        _font_cache[size] = f
    return f


def legacy_font(size):
    """Same footprint as the old pygame.font.Font(None, size) calls, so layouts don't shift."""
    return font(size * 0.68)
