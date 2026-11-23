"""Pre-baked panel textures that make the console look old, used and dirty.

Each panel is rendered once (per screen size) into an opaque surface:
grit, phosphor burn-in from text that
sat on screen for years, chipped stencil labels, rivets and a worn frame.
Blitting four opaque surfaces per frame is as cheap as the old rect fills.
"""
import random

import pygame

from config import theme
from asset_handlers import fonts


def _shade(color, delta):
    return tuple(max(0, min(255, c + delta)) for c in color)


def _settled_dirt(surf, amount):
    """Grime collects toward the bottom edge of a panel."""
    w, h = surf.get_size()
    strip = pygame.Surface((1, 32))
    for y in range(32):
        v = int(amount * (y / 31) ** 3)
        strip.set_at((0, y), (v, v, v))
    surf.blit(pygame.transform.smoothscale(strip, (w, h)), (0, 0), special_flags=pygame.BLEND_SUB)


def _grit(surf, rng, density):
    w, h = surf.get_size()
    base = theme.BG
    for _ in range(int(w * h * density)):
        x, y = rng.randrange(w), rng.randrange(h)
        if rng.random() < 0.7:
            surf.set_at((x, y), _shade(base, rng.randint(4, 14)))
        else:
            surf.set_at((x, y), (0, 0, 0))


# Old fixed screens that were left up for years and burned into the phosphor.
# Each is a header plus LABEL / VALUE rows, laid out like the form it came from.
_GHOST_FORMS = [
    ("SYS DIAGNOSTIC // 04", [
        ("AUX BUS 2", "NOMINAL"), ("REACTOR TEMP", "0412 K"), ("PWR CELL 3", "FAULT"),
        ("COOLANT LOOP B", "NOMINAL"), ("CORE MEM 640K", "OK"), ("LAST SERVICE", "2179.04.11"),
    ]),
    ("NAV ALIGNMENT // STAR FIX", [
        ("REF STAR A", "271.04"), ("REF STAR B", "118.90"), ("GYRO DRIFT", "+0.003"),
        ("PLOT ERROR", "0.41 KM"), ("FIX AGE", "00:14:22"), ("STATUS", "HOLD"),
    ]),
    ("HULL PRESSURE // DECKS 1-6", [
        ("DECK 1", "101.2 KPA"), ("DECK 2", "101.1 KPA"), ("DECK 3", "100.9 KPA"),
        ("DECK 4", "087.3 KPA"), ("DECK 5", "101.2 KPA"), ("DECK 6", "SEALED"),
    ]),
    ("COMMS // CARRIER WAVE", [
        ("BAND", "S-4"), ("SIGNAL", "NULL"), ("LAST CONTACT", "0x3F2A"),
        ("RETRIES", "0412"), ("ENCRYPT", "OFF"), ("UPLINK", "AWAITING"),
    ]),
]


def _ghost_form(surf, rng, area, form):
    """Burn a fixed readout screen into `area`: header, rule, then dot-leader rows."""
    title, rows = form
    f = fonts.font(17)
    lh = f.get_height() + 4
    col = (13, 10, 1)
    cols = max(16, (area.width - 24) // max(1, f.size("M")[0]))
    x, y = area.left + 12, area.top + 10

    def burn(text, pos):
        t = f.render_steady(text, True, col, (0, 0, 0))  # opaque black bg so BLEND_ADD only adds the glyphs
        surf.blit(t, pos, special_flags=pygame.BLEND_ADD)

    burn(title, (x, y))
    y += lh
    pygame.draw.line(surf, _shade(theme.BG, 6), (x, y - 2), (area.right - 12, y - 2))
    y += 4
    for label, value in rows:
        if y + lh > area.bottom:
            break
        dots = max(2, cols - len(label) - len(value) - 2)
        burn(f"{label} {'.' * dots} {value}", (x, y))
        y += lh
    # Faint outline of the old window, worn in places
    _worn_rect(surf, rng, area, _shade(theme.BG, 5), 1, 0.02)


def _stencil(surf, rng, label):
    """Chipped stencilled panel ID in the bottom-right corner."""
    w, h = surf.get_size()
    t = fonts.font(13).render_steady(label, True, theme.AMBER_FAINT)
    x, y = w - t.get_width() - 18, h - t.get_height() - 14
    surf.blit(t, (x, y))
    for _ in range(6):  # paint flaked off
        cx, cy = x + rng.randrange(t.get_width()), y + rng.randrange(t.get_height())
        pygame.draw.circle(surf, theme.BG, (cx, cy), rng.randint(1, 2))


def _worn_rect(surf, rng, rect, color, width, wear):
    """A rectangle border with chips, dull patches and gaps worn into it."""
    pygame.draw.rect(surf, color, rect, width)
    dull = tuple(c // 2 for c in color)
    edges = [
        (rect.left, rect.top, rect.right, rect.top),
        (rect.left, rect.bottom - 1, rect.right, rect.bottom - 1),
        (rect.left, rect.top, rect.left, rect.bottom),
        (rect.right - 1, rect.top, rect.right - 1, rect.bottom),
    ]
    for x1, y1, x2, y2 in edges:
        length = max(abs(x2 - x1), abs(y2 - y1))
        for _ in range(int(length * wear)):
            a = rng.random()
            seg = rng.randint(3, 28) / max(1, length)
            b = min(1.0, a + seg)
            p1 = (x1 + (x2 - x1) * a, y1 + (y2 - y1) * a)
            p2 = (x1 + (x2 - x1) * b, y1 + (y2 - y1) * b)
            col = theme.BG if rng.random() < 0.35 else dull
            pygame.draw.line(surf, col, p1, p2, width)


def _rivets(surf):
    w, h = surf.get_size()
    for x, y in ((14, 14), (w - 15, 14), (14, h - 15), (w - 15, h - 15)):
        pygame.draw.circle(surf, (0, 0, 0), (x + 1, y + 1), 3)
        pygame.draw.circle(surf, (24, 22, 14), (x, y), 3)
        pygame.draw.line(surf, (8, 8, 5), (x - 2, y + 1), (x + 2, y - 1))  # screw slot
        surf.set_at((x - 1, y - 2), (50, 45, 25))  # glint


def build_panel(size, seed, label, border, ghost_areas=()):
    """One panel's texture. `ghost_areas` are panel-local rects that get a burned-in old readout."""
    w, h = size
    rng = random.Random(seed)
    surf = pygame.Surface((w, h))
    surf.fill(theme.BG)

    if theme.GRIME_ENABLED:
        _settled_dirt(surf, 6)
        forms = rng.sample(_GHOST_FORMS, min(len(ghost_areas), len(_GHOST_FORMS)))
        for area, form in zip(ghost_areas, forms):
            _ghost_form(surf, rng, pygame.Rect(area), form)
        _grit(surf, rng, 0.012)
        _stencil(surf, rng, label)
        _rivets(surf)
        _worn_rect(surf, rng, surf.get_rect(), border, 2, 0.012)
    else:
        pygame.draw.rect(surf, border, surf.get_rect(), 2)
    return surf
