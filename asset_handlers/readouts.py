"""Dim background terminals that type out randomly generated machine chatter.

They're set dressing, not information: the ship's computers muttering to
themselves in the empty top panel. Each terminal types one line at a time,
pauses, and scrolls. All timing is wall-clock, so frame rate doesn't matter.
"""
import random

import pygame

from utility import theme
from asset_handlers import fonts

COLOR_OLD = (40, 29, 0)     # lines already printed
COLOR_NEW = (75, 54, 0)     # the line being typed
COLOR_TITLE = (55, 40, 0)


def _hex(n):
    return "".join(random.choice("0123456789ABCDEF") for _ in range(n))


def syslog_line():
    r = random.random
    return random.choice([
        lambda: f"MEM SCRUB {_hex(4)}-{_hex(4)} .. OK",
        lambda: f"COOLANT LOOP {random.choice('ABC')} {random.randint(280, 320)}K NOMINAL",
        lambda: f"NAV SYNC DRIFT {r() * 0.01 - 0.005:+.4f}",
        lambda: f"BUS {random.randint(1, 6)} > BUS {random.randint(1, 6)} HANDSHAKE OK",
        lambda: f"RAD SHIELD {random.randint(91, 100)}%",
        lambda: f"PWR CELL {random.randint(1, 4)} {random.randint(60, 99)}% DRAW {random.randint(2, 9)}.{random.randint(0, 9)}KW",
        lambda: "LIFE SUPPORT NOMINAL",
        lambda: f"WATCHDOG TICK {random.randint(0, 65535):05d}",
        lambda: f"SENSOR CAL CH{random.randint(1, 16):02d} {r() * 2 - 1:+.3f}",
        lambda: f"WARN PARITY ERR 0x{_hex(4)} RETRY {random.randint(1, 3)}/3",
        lambda: f"HULL STRAIN FRAME {random.randint(1, 40):02d} {random.randint(0, 40)} UE",
        lambda: "GYRO SPIN-UP ... OK",
    ])()


def memdump_line():
    data = [_hex(2) for _ in range(8)]
    ascii_ = "".join(chr(int(b, 16)) if 0x30 <= int(b, 16) <= 0x5A else "." for b in data)
    return f"0x{_hex(4)}  {' '.join(data)}  {ascii_}"


def comms_line():
    return random.choice([
        lambda: f"RX PKT {random.randint(0, 99999):05d} CRC FAIL",
        lambda: f"RX PKT {random.randint(0, 99999):05d} OK {random.randint(32, 512)}B",
        lambda: f"CARRIER S-{random.randint(1, 6)} {random.randint(-120, -60)}DBM",
        lambda: f"BEACON {_hex(3)} OUT OF RANGE",
        lambda: "HAILING ... NO RESPONSE",
        lambda: f"HANDSHAKE {_hex(4)}:{_hex(4)} TIMEOUT",
        lambda: f"TX QUEUE {random.randint(0, 12)} PENDING",
        lambda: f"STATIC BURST {random.randint(1, 9)}.{random.randint(0, 9)}S",
        lambda: "UPLINK HELD",
    ])()


class Terminal:
    def __init__(self, title, generator, chars_per_sec=38, pause=(0.6, 3.5)):
        self.title = title
        self.generator = generator
        self.cps = chars_per_sec
        self.pause = pause
        self.lines = []           # finished lines, cached surfaces
        self.current = generator()
        self.started = 0          # ms the current line began typing
        self.next_start = 0       # ms the next line may begin
        self.font = fonts.font(15)

    def _advance(self, now):
        if self.next_start == 0:
            self.started = now + random.randint(0, 2000)  # stagger terminals at startup
            self.next_start = -1
        speed = max(0.05, theme.READOUT_SPEED)
        typed = int((now - self.started) / 1000 * self.cps * speed)
        if typed >= len(self.current) and self.next_start < 0:
            self.next_start = now + int(random.uniform(*self.pause) * 1000 / speed)
        if self.next_start > 0 and now >= self.next_start:
            self.lines.append(self.font.render_steady(self.current, True, COLOR_OLD))
            self.lines = self.lines[-20:]
            self.current = self.generator()
            self.started = now
            self.next_start = -1
        return max(0, min(len(self.current), typed))

    def draw(self, screen, rect):
        now = pygame.time.get_ticks()
        typed = self._advance(now)
        f = self.font
        lh = f.get_height() + 1

        title = f.render_steady(self.title, True, COLOR_TITLE)
        screen.blit(title, (rect.left, rect.top))
        rule_y = rect.top + title.get_height() + 2
        pygame.draw.line(screen, theme.AMBER_FAINT, (rect.left, rule_y), (rect.right, rule_y))

        body_top = rule_y + 5
        rows = max(1, (rect.bottom - body_top) // lh)
        old = self.lines[-(rows - 1):] if rows > 1 else []
        y = body_top
        clip = screen.get_clip()
        screen.set_clip(rect)
        for surf in old:
            screen.blit(surf, (rect.left, y))
            y += lh
        # Line being typed, with a block cursor that blinks once the line is done
        shown = self.current[:typed]
        surf = f.render(shown, True, COLOR_NEW) if shown else None  # can flicker like other live text
        if surf:
            screen.blit(surf, (rect.left, y))
        cursor_on = typed < len(self.current) or (now // 400) % 2 == 0
        if cursor_on:
            cx = rect.left + f.size(shown)[0] + 2
            pygame.draw.rect(screen, COLOR_NEW, (cx, y + 2, f.size("M")[0], f.get_height() - 4))
        screen.set_clip(clip)


class TopPanelReadouts:
    """Terminals spread across the top panel, either side of anything in `exclude`."""

    MIN_WIDTH = 150  # narrower than this and a terminal isn't worth drawing

    def __init__(self):
        self.terminals = [
            Terminal("SYS LOG", syslog_line),
            Terminal("CORE MEMORY", memdump_line, chars_per_sec=70, pause=(0.1, 0.8)),
            Terminal("COMMS", comms_line, chars_per_sec=30, pause=(1.5, 6.0)),
        ]

    def draw(self, screen, panel_rect, exclude=None):
        """exclude: a box at the left of the panel (the pilot ID) to keep clear.
        The terminals share what is between."""
        if not theme.GRIME_ENABLED:
            return
        inner = panel_rect.inflate(-60, -44)
        gap = 50
        if exclude is not None:
            inner.width -= exclude.right + gap - inner.left
            inner.left = exclude.right + gap
        w = (inner.width - gap * (len(self.terminals) - 1)) // len(self.terminals)
        if w < self.MIN_WIDTH:
            return
        for i, term in enumerate(self.terminals):
            term.draw(screen, pygame.Rect(inner.left + i * (w + gap), inner.top, w, inner.height))
