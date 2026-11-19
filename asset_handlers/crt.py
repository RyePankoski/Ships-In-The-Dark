import math
import random

import pygame

from utility import theme


class CRTFilter:
    """Full-screen post-processing that makes the whole frame read as one old monitor.

    1. Tearing: now and then a strip of the picture jumps sideways (bad sync).
    2. Glow: shrink the frame, stretch it back up (which blurs it), and add it on
       top. Bright lines bleed light; the dark background stays dark.
    3. Hum bar: a faint bright band that rolls slowly down the tube.
    4. Static overlay: scanlines, a brownish vignette, and dirt on the glass
       (dust, smudges, scratches). Precomputed, rebuilt only if the window size changes.
    5. Grain: animated static, tiled from a few small precomputed noise tiles.
    6. Flicker: the odd frame where the whole tube sags.

    Applied once per frame in utility.util.end_blit, so every screen gets it.
    """

    GRAIN_TILE = 256
    GRAIN_FRAMES = 4
    HUM_HEIGHT = 180

    def __init__(self):
        self.enabled = theme.CRT_ENABLED
        self._overlay = None
        self._overlay_size = None
        self._hum = None
        self._grain = None

    def toggle(self):
        self.enabled = not self.enabled

    def apply(self, screen):
        if not self.enabled:
            return
        size = screen.get_size()
        if self._overlay_size != size:
            self._overlay = self._build_overlay(size)
            self._hum = self._build_hum(size[0])
            self._overlay_size = size
        if self._grain is None:
            self._grain = self._build_grain()

        self._tear(screen)
        self._glow(screen)
        self._hum_bar(screen)
        screen.blit(self._overlay, (0, 0))
        self._static(screen)
        if theme.FLICKER_CHANCE > 0 and random.random() < theme.FLICKER_CHANCE:
            v = random.randint(200, 235)
            screen.fill((v, v, v), special_flags=pygame.BLEND_MULT)

    # ------------------------------------------------------------------
    # Per-frame effects
    # ------------------------------------------------------------------
    @staticmethod
    def _tear(screen):
        if theme.TEAR_CHANCE <= 0 or random.random() >= theme.TEAR_CHANCE:
            return
        w, h = screen.get_size()
        # A few adjacent strips slide by different amounts, like a sync hiccup
        y = random.randrange(h)
        for _ in range(random.randint(1, 3)):
            sh = random.randint(2, 24)
            rect = pygame.Rect(0, y, w, sh).clip(screen.get_rect())
            if rect.height <= 0:
                break
            strip = screen.subsurface(rect).copy()
            dx = random.choice((-1, 1)) * random.randint(3, 18)
            screen.fill((0, 0, 0), rect)
            screen.blit(strip, (dx, rect.y))
            y += sh

    def _hum_bar(self, screen):
        if theme.HUM_BAR_STRENGTH <= 0:
            return
        h = screen.get_height()
        span = h + self.HUM_HEIGHT
        y = int(pygame.time.get_ticks() * theme.HUM_BAR_SPEED) % span - self.HUM_HEIGHT
        screen.blit(self._hum, (0, y), special_flags=pygame.BLEND_ADD)

    def _static(self, screen):
        if theme.GRAIN_STRENGTH <= 0:
            return
        w, h = screen.get_size()
        t = self.GRAIN_TILE
        tile = random.choice(self._grain)
        ox, oy = random.randrange(t), random.randrange(t)
        for y in range(-oy, h, t):
            for x in range(-ox, w, t):
                screen.blit(tile, (x, y), special_flags=pygame.BLEND_ADD)

    @staticmethod
    def _glow(screen):
        if theme.GLOW_STRENGTH <= 0:
            return
        # Every full-resolution operation costs milliseconds at 1080p, so all the
        # real work (blur, dimming) happens on the small copy.
        w, h = screen.get_size()
        d = max(2, theme.GLOW_DOWNSCALE)
        half = pygame.transform.scale(screen, (max(1, w // 2), max(1, h // 2)))
        small = pygame.transform.smoothscale(half, (max(1, w // d), max(1, h // d)))
        # A second, smaller pass widens the blur cheaply
        smaller = pygame.transform.smoothscale(small, (max(1, w // (d * 2)), max(1, h // (d * 2))))
        small = pygame.transform.smoothscale(smaller, small.get_size())
        s = theme.GLOW_STRENGTH
        small.fill((s, s, s), special_flags=pygame.BLEND_MULT)
        glow = pygame.transform.smoothscale(small, (max(1, w // 2), max(1, h // 2)))
        glow = pygame.transform.scale(glow, (w, h))
        screen.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

    # ------------------------------------------------------------------
    # Precomputed layers
    # ------------------------------------------------------------------
    def _build_grain(self):
        t = self.GRAIN_TILE
        g = theme.GRAIN_STRENGTH
        rng = random.Random()
        tiles = []
        for _ in range(self.GRAIN_FRAMES):
            tile = pygame.Surface((t, t))
            tile.fill((0, 0, 0))
            # Sparse speckles, tinted slightly green like a phosphor
            for _ in range(t * t // 6):
                v = int(g * rng.random() ** 2)
                if v:
                    tile.set_at((rng.randrange(t), rng.randrange(t)), (v * 3 // 4, v, v * 2 // 3))
            tiles.append(tile)
        return tiles

    def _build_hum(self, w):
        hh = self.HUM_HEIGHT
        strip = pygame.Surface((1, hh))
        for y in range(hh):
            v = int(theme.HUM_BAR_STRENGTH * math.sin(math.pi * y / (hh - 1)) ** 2)
            strip.set_at((0, y), (v, v, v * 3 // 4))
        return pygame.transform.scale(strip, (w, hh))

    @staticmethod
    def _build_overlay(size):
        w, h = size
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        rng = random.Random(1983)  # same dirty glass every launch

        # Vignette: compute at low resolution, then stretch (smooth for free).
        # Tinted a burnt brown rather than pure black, like a yellowed old tube.
        vw, vh = 96, 54
        vignette = pygame.Surface((vw, vh), pygame.SRCALPHA)
        for y in range(vh):
            for x in range(vw):
                nx = (x + 0.5) / vw * 2 - 1
                ny = (y + 0.5) / vh * 2 - 1
                r = math.hypot(nx, ny) / math.sqrt(2)  # 0 centre, 1 corner
                a = max(0.0, (r - 0.55) / 0.45)
                vignette.set_at((x, y), (10, 6, 0, int(theme.VIGNETTE_ALPHA * a * a)))
        overlay.blit(pygame.transform.smoothscale(vignette, size), (0, 0))

        dirt = theme.GLASS_DIRT
        if dirt > 0:
            glass = pygame.Surface(size, pygame.SRCALPHA)

            # Smudges / fingerprint haze: soft milky blobs, built small and stretched
            sw, sh = max(2, w // 4), max(2, h // 4)
            smudge = pygame.Surface((sw, sh), pygame.SRCALPHA)
            for _ in range(int(10 * dirt)):
                cx, cy = rng.randrange(sw), rng.randrange(sh)
                rad = rng.randint(10, 45)
                blob = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
                for rr in range(rad, 0, -2):  # stacked faint discs = soft radial falloff
                    pygame.draw.circle(blob, (190, 180, 150, max(1, int(dirt))), (rad, rad), rr)
                blob = pygame.transform.smoothscale(blob, (rad * 2, int(rad * 2 * rng.uniform(0.5, 1.0))))
                smudge.blit(blob, (cx - rad, cy - rad))
            glass.blit(pygame.transform.smoothscale(smudge, size), (0, 0))

            # Dust specks
            for _ in range(int(w * h / 2500 * dirt)):
                x, y = rng.randrange(w), rng.randrange(h)
                a = rng.randint(25, 80)
                if rng.random() < 0.85:
                    glass.set_at((x, y), (170, 160, 140, a))
                else:
                    pygame.draw.circle(glass, (150, 140, 120, a // 2), (x, y), rng.randint(1, 2))

            # Hairline scratches in the glass
            for _ in range(int(6 * dirt)):
                x, y = rng.randrange(w), rng.randrange(h)
                ang = rng.uniform(0, math.tau)
                length = rng.randint(40, 260)
                pts = [(x, y)]
                for _ in range(length // 10):
                    ang += rng.uniform(-0.08, 0.08)
                    x += math.cos(ang) * 10
                    y += math.sin(ang) * 10
                    pts.append((x, y))
                pygame.draw.aalines(glass, (200, 195, 170, int(28 * dirt)), False, pts)

            overlay.blit(glass, (0, 0))

        # Scanlines on top
        lines = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(0, h, theme.SCANLINE_SPACING):
            pygame.draw.line(lines, (0, 0, 0, theme.SCANLINE_ALPHA), (0, y), (w, y))
        overlay.blit(lines, (0, 0))
        return overlay


crt = CRTFilter()
