"""The operator console: the Esc menu, its controls reference and the manual.

This is the player stepping back from the cockpit, not a pause: the ship and
the world keep running underneath (in multiplayer they have to), and the
wording says so. While it's open, the cockpit's keys and buttons are off;
ship movement still runs.
"""
import pygame

from config import theme
from asset_handlers.buttons import draw_blank_underlay
from asset_handlers.ui_scale import px, ui_font
from config.manual import *


def _put(screen, surf, **where):
    """Blit text straight onto the blanked feed, on a black backing so it stays readable.
    `where` is a get_rect anchor, e.g. topleft=(x, y)."""
    rect = surf.get_rect(**where)
    pygame.draw.rect(screen, theme.BLACK, rect.inflate(px(14), px(4)))
    screen.blit(surf, rect)


class PauseMenu:
    # Which screen is showing
    CONSOLE, CONTROLS, MANUAL = 'console', 'controls', 'manual'

    # Keys per screen -> this class's own action names. Clicks use the same names.
    CONSOLE_KEYS = {pygame.K_ESCAPE: 'resume', pygame.K_c: 'controls', pygame.K_m: 'manual', pygame.K_q: 'quit'}
    CONTROLS_KEYS = {pygame.K_ESCAPE: 'back', pygame.K_c: 'back'}
    MANUAL_KEYS = {pygame.K_ESCAPE: 'back', pygame.K_m: 'back', pygame.K_LEFT: 'prev', pygame.K_RIGHT: 'next'}

    # Console options: (label, key hint, action)
    OPTIONS = (
        ("RETURN TO COCKPIT", "ESC", 'resume'),
        ("CONTROLS", "C", 'controls'),
        ("MANUAL", "M", 'manual'),
        ("QUIT TO MENU", "Q", 'quit'),
    )

    # Shown on the controls screen. Left column, then right column; each is a
    # list of (section title, [(key, description), ...]). Keep in sync with
    # MainScene.handle_inputs.
    CONTROLS_LAYOUT = (
        [
            ("FLIGHT", [
                ("W S", "THRUST / REVERSE"),
                ("A D", "TURN"),
                ("SHIFT + A D", "SLIDE LEFT / RIGHT"),
                ("TAB", "BRAKE (HOLD)"),
                ("G", "INERT DAMPENER ON / OFF"),
                ("T", "BLINK DRIVE"),
            ]),
            ("WEAPONS", [
                ("P", "FIRE MISSILE AT TARGET"),
                ("R-ALT", "DEPLOY DECOY"),
                ("E", "MINING LASER ON / OFF"),
            ]),
            ("DISPLAYS", [
                ("M", "TACTICAL MAP"),
                ("H", "HEADING / VELOCITY VECTORS"),
                ("F9", "CRT FILTER"),
                ("ESC", "CONSOLE / CLOSE"),
            ]),
        ],
        [
            ("LASER", [
                ("I", "LASER ON / OFF"),
                ("LEFT RIGHT", "SWEEP LASER"),
                ("SPACE", "LOCK / RELEASE"),
                ("N", "MATERIAL SCAN"),
            ]),
            ("SENSORS", [
                ("R", "RADAR SWEEP"),
                ("Q", "CLOSE RANGE SCAN"),
            ]),
            ("DEEP FIELD SCANNER", [
                ("K", "DFS ON / OFF"),
                ("UP DOWN", "CHANGE BEARING"),
                ("O", "RUN SCAN"),
            ]),
        ],
    )

    # Shown on the manual screen, one topic per page: (section title, body text).
    # The body is word-wrapped to the page; it shrinks if it would run off the bottom.
    MANUAL_PLACEHOLDER = "TO BE WRITTEN"
    MANUAL_PAGES = (
        ("LASER ASSESSOR", LASER_ASSESSOR_MANUAL.upper()),
        ("MATERIAL ASSESSOR", MATERIAL_ASSESSOR_MANUAL.upper()),

        ("MISSILES", MISSILE_MANUAL.upper()),
        ("DECOY", DECOY_MANUAL.upper()),
        ("ASTEROIDS", ASTEROID_MANUAL.upper()),

        ("RADAR", RADAR_MANUAL.upper()),
        ("DEEP FIELD SCANNER", DEEP_FIELD_SCANNER_MANUAL.upper()),
        ("CLOSE RANGE SCAN", PROX_MANUAL.upper()),

        ("TACTICAL MAP", TACTICAL_MAP_MANUAL.upper()),
        ("FUEL", FUEL_MANUAL.upper()),
        ("INERT DAMPENER", INERT_DAMPENER_MANUAL.upper()),

        ("BLINK DRIVE", BLINK_DRIVE_MANUAL.upper()),

    )

    def __init__(self):
        self.is_open = False
        self.page = self.CONSOLE
        self.manual_page = 0

    @property
    def showing_controls(self):
        return self.page == self.CONTROLS

    def open(self):
        self.is_open = True
        self.page = self.CONSOLE

    def handle(self, events, clicks):
        keymap = {
            self.CONSOLE: self.CONSOLE_KEYS,
            self.CONTROLS: self.CONTROLS_KEYS,
            self.MANUAL: self.MANUAL_KEYS,
        }[self.page]
        keys = [keymap[event.key] for event in events
                if event.type == pygame.KEYDOWN and event.key in keymap]

        for action in (*clicks, *keys):
            if action == 'resume':
                self.is_open = False
                self.page = self.CONSOLE
                return 'resume'
            if action == 'quit':
                return 'quit'
            if action == 'controls':
                self.page = self.CONTROLS
            elif action == 'manual':
                self.page = self.MANUAL
                self.manual_page = 0
            elif action.startswith('page:'):
                self.manual_page = int(action[len('page:'):])
            elif action == 'prev':
                self.manual_page = max(0, self.manual_page - 1)
            elif action == 'next':
                self.manual_page = min(len(self.MANUAL_PAGES) - 1, self.manual_page + 1)
            elif action == 'back':
                self.page = self.CONSOLE
        return None

    def draw(self, screen, buttons):
        """Draw the current screen over the game, and register its buttons.

        Draw the game frame first, then call this. Nothing
        drawn underneath stays clickable.
        """
        if not self.is_open:
            return
        if self.page == self.MANUAL:
            # Opaque: the manual is reading material, so the feed doesn't show through
            screen.fill(theme.BG)
        else:
            draw_blank_underlay(screen)
        buttons.block_below()
        if self.page == self.CONTROLS:
            self._draw_controls(screen, buttons)
        elif self.page == self.MANUAL:
            self._draw_manual(screen, buttons)
        else:
            self._draw_console(screen, buttons)

    def _draw_console(self, screen, buttons):
        w, h = screen.get_size()
        t = pygame.time.get_ticks() / 1000.0

        title_font = ui_font(64)
        body_font = ui_font(32)
        small_font = ui_font(22)

        # No card: everything hangs off one left margin, straight on the blanked feed
        line_h = px(78)
        x0, top = px(48), px(40)

        # Header strip
        header = small_font.render("UPLINK HELD  //  SHIP STILL LIVE", True, theme.AMBER_DIM)
        _put(screen, header, topleft=(x0, top))

        # Title
        title = title_font.render("OPERATOR CONSOLE", True, theme.AMBER_BRIGHT)
        _put(screen, title, topleft=(x0, top + px(30)))

        # Options
        y = top + px(136)
        for label, key, action in self.OPTIONS:
            rect = pygame.Rect(x0, y, px(520), line_h - px(12))
            buttons.button(screen, rect, label, action, key=key, align="left", font=body_font,
                           key_font=ui_font(18))
            y += line_h

        # Status line at the bottom, with a blinking input cursor
        cursor = "_" if int(t * 2) % 2 == 0 else " "
        footer = small_font.render(f"STATUS: PAUSED  //  AWAITING INPUT {cursor}", True, theme.AMBER_DIM)
        _put(screen, footer, bottomleft=(x0, h - px(32)))

    def _draw_controls(self, screen, buttons):
        w, h = screen.get_size()

        title_font = ui_font(54)
        row_font = ui_font(27)
        section_font = ui_font(24)
        small_font = ui_font(21)

        row_h = row_font.get_height() + px(8)
        section_gap = px(24)
        section_h = section_font.get_height() + px(10)
        key_col_w = px(200)
        col_w = px(540)
        col_gap = px(64)

        def column_height(sections):
            return sum(section_h + len(rows) * row_h for _, rows in sections) + section_gap * (len(sections) - 1)

        body_h = max(column_height(col) for col in self.CONTROLS_LAYOUT)
        left, top = px(48), px(40)

        header = small_font.render("OPERATOR CONSOLE  //  INPUT MAP", True, theme.AMBER_DIM)
        _put(screen, header, topleft=(left, top))
        title = title_font.render("CONTROLS", True, theme.AMBER_BRIGHT)
        _put(screen, title, topleft=(left, top + px(30)))

        body_top = top + px(120)
        divider_x = left + col_w + col_gap // 2
        pygame.draw.line(screen, theme.AMBER_FAINT,
                         (divider_x, body_top), (divider_x, body_top + body_h), px(1))

        for col_index, sections in enumerate(self.CONTROLS_LAYOUT):
            x = left + col_index * (col_w + col_gap)
            y = body_top
            for section_title, rows in sections:
                # Section heading with a rule running out to the column edge
                heading = section_font.render(section_title, True, theme.AMBER)
                _put(screen, heading, topleft=(x, y))
                rule_y = y + heading.get_height() // 2
                pygame.draw.line(screen, theme.AMBER_DIM,
                                 (x + heading.get_width() + px(10), rule_y), (x + col_w, rule_y), px(1))
                y += section_h

                for key, description in rows:
                    # Plain tabulated key column, no outlined keycaps (that's <kbd> styling)
                    key_surf = row_font.render(key, True, theme.GREEN_BRIGHT)
                    _put(screen, key_surf, topleft=(x + px(8), y))
                    desc_surf = row_font.render(description, True, theme.GREEN)
                    _put(screen, desc_surf, topleft=(x + key_col_w, y))
                    y += row_h
                y += section_gap

        back = pygame.Rect(0, 0, px(260), px(50))
        back.bottomleft = (left, h - px(40))
        buttons.button(screen, back, "BACK", 'back', key="ESC", align="left", font=row_font)

    @staticmethod
    def _wrap(font, text, width):
        """Split text into lines no wider than `width` pixels, breaking between words."""
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}" if line else word
            if font.size(trial)[0] <= width:
                line = trial
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def _manual_tab_rects(self, width, left, top):
        """Lay the topic tabs out left to right, wrapping onto new rows as needed.
        Returns one Rect per entry in MANUAL_PAGES."""
        font = ui_font(20)
        pad, gap, row_h, row_gap = px(16), px(8), px(40), px(8)
        rects, x, y = [], left, top
        for title, _ in self.MANUAL_PAGES:
            tab_w = font.size(title)[0] + 2 * pad
            if x + tab_w > left + width and x > left:
                x = left
                y += row_h + row_gap
            rects.append(pygame.Rect(x, y, tab_w, row_h))
            x += tab_w + gap
        return rects

    def _draw_manual(self, screen, buttons):
        w, h = screen.get_size()
        left, top = px(48), px(40)
        margin = left
        text_w = w - 2 * margin

        title, body = self.MANUAL_PAGES[self.manual_page]
        last = len(self.MANUAL_PAGES) - 1

        # Bottom row: BACK on the left; PREV, page count and NEXT on the right
        nav_h = px(50)
        nav_top = h - px(40) - nav_h
        row_font = ui_font(27)
        back = pygame.Rect(left, nav_top, px(260), nav_h)
        buttons.button(screen, back, "BACK", 'back', key="ESC", align="left", font=row_font)

        prev_rect = pygame.Rect(w - margin - px(2 * 150 + 16), nav_top, px(150), nav_h)
        next_rect = pygame.Rect(w - margin - px(150), nav_top, px(150), nav_h)
        buttons.button(screen, prev_rect, "PREV", 'prev', key="<-", align="left", font=row_font,
                       enabled=self.manual_page > 0)
        buttons.button(screen, next_rect, "NEXT", 'next', key="->", align="left", font=row_font,
                       enabled=self.manual_page < last)

        # The page is opaque, so text is drawn straight on it (no black backing boxes)
        def blit(surf, **where):
            screen.blit(surf, surf.get_rect(**where))

        counter = ui_font(22).render(f"{self.manual_page + 1} / {last + 1}", True, theme.AMBER_DIM)
        blit(counter, midbottom=(w // 2, nav_top + nav_h))

        # Header strip
        header = ui_font(21).render("OPERATOR CONSOLE  //  MANUAL", True, theme.AMBER_DIM)
        blit(header, topleft=(left, top))

        # Topic tabs: click one to jump straight to that topic. The open one gets a bright border.
        tab_font = ui_font(20)
        tabs_top = top + px(36)
        tab_rects = self._manual_tab_rects(text_w, left, tabs_top)
        for index, ((tab_title, _), rect) in enumerate(zip(self.MANUAL_PAGES, tab_rects)):
            buttons.button(screen, rect, tab_title, f"page:{index}", align="left", font=tab_font)
            if index == self.manual_page:
                pygame.draw.rect(screen, theme.AMBER_BRIGHT, rect, px(2))
        tabs_bottom = max(rect.bottom for rect in tab_rects)

        # The topic's title, with a rule to the right edge
        title_surf = ui_font(44).render(title, True, theme.AMBER_BRIGHT)
        title_y = tabs_bottom + px(18)
        blit(title_surf, topleft=(left, title_y))
        rule_y = title_y + title_surf.get_height() + px(8)
        pygame.draw.line(screen, theme.AMBER_DIM, (left, rule_y), (w - margin, rule_y), px(1))

        # Body: wrap at the largest size that fits between the rule and the nav row
        body_top = rule_y + px(18)
        body_bottom = nav_top - px(30)
        for size in (30, 28, 26, 24, 22, 20):
            body_font = ui_font(size)
            lines = self._wrap(body_font, body, text_w - px(16))
            line_h = body_font.get_linesize()
            if body_top + len(lines) * line_h <= body_bottom:
                break
        y = body_top
        for line in lines:
            blit(body_font.render(line, True, theme.GREEN), topleft=(left + px(8), y))
            y += line_h
