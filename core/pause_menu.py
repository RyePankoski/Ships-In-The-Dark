"""The operator console: the Esc menu and its controls reference.

This is the player stepping back from the cockpit, not a pause: the ship and
the world keep running underneath (in multiplayer they have to), and the
wording says so. While it's open, the cockpit's keys and buttons are off;
ship movement still runs.
"""
import pygame

from utility import theme
from asset_handlers import fonts
from asset_handlers.buttons import draw_blank_underlay


def _put(screen, surf, **where):
    """Blit text straight onto the blanked feed, on a black backing so it stays readable.
    `where` is a get_rect anchor, e.g. topleft=(x, y)."""
    rect = surf.get_rect(**where)
    pygame.draw.rect(screen, theme.BLACK, rect.inflate(14, 4))
    screen.blit(surf, rect)


class PauseMenu:
    # Keys per screen -> this class's own action names. Clicks use the same names.
    CONSOLE_KEYS = {'esc': 'resume', 'c': 'controls', 'q': 'quit'}
    CONTROLS_KEYS = {'esc': 'back', 'c': 'back'}
    # Keys that the input cooldown should count as a press
    KEYS = ('esc', 'c', 'q')

    # Console options: (label, key hint, action)
    OPTIONS = (
        ("RETURN TO COCKPIT", "ESC", 'resume'),
        ("CONTROLS", "C", 'controls'),
        ("QUIT TO MENU", "Q", 'quit'),
    )

    # Shown on the controls screen. Left column, then right column; each is a
    # list of (section title, [(key, description), ...]). Keep in sync with
    # MainScene.KEY_ACTIONS and the instruments' keys.
    CONTROLS_LAYOUT = (
        [
            ("FLIGHT", [
                ("W A S D", "THRUST"),
                ("TAB", "BRAKE (HOLD)"),
                ("G", "INERT DAMPENER ON / OFF"),
                ("T", "BLINK DRIVE"),
            ]),
            ("WEAPONS", [
                ("P", "FIRE MISSILE AT TARGET"),
                ("R-ALT", "DEPLOY DECOY"),
            ]),
            ("DISPLAYS", [
                ("M", "TACTICAL MAP"),
                ("N", "P-FIELD SCANNER"),
                ("F9", "CRT FILTER"),
                ("ESC", "CONSOLE / CLOSE"),
            ]),
        ],
        [
            ("LASER", [
                ("I", "LASER ON / OFF"),
                ("LEFT RIGHT", "SWEEP LASER"),
                ("SPACE", "LOCK / RELEASE"),
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

    def __init__(self):
        self.is_open = False
        self.showing_controls = False

    def open(self):
        self.is_open = True
        self.showing_controls = False

    def handle(self, inputs, clicks, keys_live):
        """Act on this frame's clicks and key presses while the menu is open.

        Args:
            inputs: The frame's key states (see utility.common.collect_inputs).
            clicks: Actions of the menu buttons clicked this frame.
            keys_live: False while the input cooldown is running; keys are ignored then.

        Returns:
            'resume' when the menu has closed and the player is back in the cockpit,
            'quit' when they chose QUIT TO MENU, or None.
        """
        keymap = self.CONTROLS_KEYS if self.showing_controls else self.CONSOLE_KEYS
        keys = [action for key, action in keymap.items() if keys_live and inputs.get(key)]

        for action in (*clicks, *keys):
            if action == 'resume':
                self.is_open = False
                self.showing_controls = False
                return 'resume'
            if action == 'quit':
                # Stays open: the scene blacks out behind it while the shutdown plays
                return 'quit'
            if action == 'controls':
                self.showing_controls = True
            elif action == 'back':
                self.showing_controls = False
        return None

    def draw(self, screen, buttons, underlay=True):
        """Draw the current screen over the game, and register its buttons.

        Draw the game frame first, then call this, then end_blit(). Nothing
        drawn underneath stays clickable. underlay=False skips the blanked
        feed, for when the caller has already blacked the screen out.
        """
        if not self.is_open:
            return
        if underlay:
            draw_blank_underlay(screen)
        buttons.block_below()
        if self.showing_controls:
            self._draw_controls(screen, buttons)
        else:
            self._draw_console(screen, buttons)

    def _draw_console(self, screen, buttons):
        w, h = screen.get_size()
        t = pygame.time.get_ticks() / 1000.0

        title_font = fonts.font(64)
        body_font = fonts.font(32)
        small_font = fonts.font(22)

        # No card: everything hangs off one left margin, straight on the blanked feed
        line_h = 78
        x0, top = 48, 40

        # Header strip
        header = small_font.render("UPLINK HELD  //  SHIP STILL LIVE", True, theme.AMBER_DIM)
        _put(screen, header, topleft=(x0, top))

        # Title
        title = title_font.render("OPERATOR CONSOLE", True, theme.AMBER_BRIGHT)
        _put(screen, title, topleft=(x0, top + 30))

        # Options
        y = top + 136
        for label, key, action in self.OPTIONS:
            rect = pygame.Rect(x0, y, 520, line_h - 12)
            buttons.button(screen, rect, label, action, key=key, align="left", font=body_font,
                           key_font=fonts.font(18))
            y += line_h

        # Status line at the bottom, with a blinking input cursor
        cursor = "_" if int(t * 2) % 2 == 0 else " "
        footer = small_font.render(f"STATUS: PAUSED  //  AWAITING INPUT {cursor}", True, theme.AMBER_DIM)
        _put(screen, footer, bottomleft=(x0, h - 32))

    def _draw_controls(self, screen, buttons):
        w, h = screen.get_size()

        title_font = fonts.font(54)
        row_font = fonts.font(27)
        section_font = fonts.font(24)
        small_font = fonts.font(21)

        row_h = row_font.get_height() + 8
        section_gap = 24
        section_h = section_font.get_height() + 10
        key_col_w = 200
        col_w = 540
        col_gap = 64

        def column_height(sections):
            return sum(section_h + len(rows) * row_h for _, rows in sections) + section_gap * (len(sections) - 1)

        body_h = max(column_height(col) for col in self.CONTROLS_LAYOUT)
        left, top = 48, 40

        header = small_font.render("OPERATOR CONSOLE  //  INPUT MAP", True, theme.AMBER_DIM)
        _put(screen, header, topleft=(left, top))
        title = title_font.render("CONTROLS", True, theme.AMBER_BRIGHT)
        _put(screen, title, topleft=(left, top + 30))

        body_top = top + 120
        divider_x = left + col_w + col_gap // 2
        pygame.draw.line(screen, theme.AMBER_FAINT,
                         (divider_x, body_top), (divider_x, body_top + body_h), 1)

        for col_index, sections in enumerate(self.CONTROLS_LAYOUT):
            x = left + col_index * (col_w + col_gap)
            y = body_top
            for section_title, rows in sections:
                # Section heading with a rule running out to the column edge
                heading = section_font.render(section_title, True, theme.AMBER)
                _put(screen, heading, topleft=(x, y))
                rule_y = y + heading.get_height() // 2
                pygame.draw.line(screen, theme.AMBER_DIM,
                                 (x + heading.get_width() + 10, rule_y), (x + col_w, rule_y), 1)
                y += section_h

                for key, description in rows:
                    # Plain tabulated key column, no outlined keycaps (that's <kbd> styling)
                    key_surf = row_font.render(key, True, theme.GREEN_BRIGHT)
                    _put(screen, key_surf, topleft=(x + 8, y))
                    desc_surf = row_font.render(description, True, theme.GREEN)
                    _put(screen, desc_surf, topleft=(x + key_col_w, y))
                    y += row_h
                y += section_gap

        back = pygame.Rect(0, 0, 260, 50)
        back.bottomleft = (left, h - 40)
        buttons.button(screen, back, "BACK", 'back', key="ESC", align="left", font=row_font)
