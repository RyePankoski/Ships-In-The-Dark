import math
import zlib
import random

import pygame
from utility.constants import *
from utility import theme
from asset_handlers import fonts
from asset_handlers.buttons import ButtonLayer, draw_button, draw_frame
from asset_handlers.grime import build_panel
from asset_handlers.readouts import TopPanelReadouts
from utility.common import end_blit, blink_cursor


class DrawUI:
    # region constant
    PANEL_WIDTH = 600
    THIN_HEIGHT = 200

    # Radar Configuration
    RADAR_PADDING = 20
    RADAR_SCALE = 4000.0  # World units (±2000 in each direction)
    RADAR_GRID_COUNT = 2

    # Corridor Dimensions
    CORRIDOR_WIDTH = CORRIDOR_WIDTH
    CORRIDOR_DEPTH = CORRIDOR_DEPTH

    # DFS Configuration
    DFS_MAX_RANGE = 5000
    DFS_PANEL_MARGIN = 20
    DFS_CONTACT_DISPLAY_LIMIT = 8

    # Missile Vector Display
    MISSILE_VECTOR_LENGTH = 75

    # Colour palette: see utility/theme.py for what each colour means
    COLOR_PANEL_BG = theme.BG
    COLOR_BORDER_PRIMARY = theme.AMBER
    COLOR_BORDER_INSET = theme.AMBER_DIM
    COLOR_DATA = theme.GREEN
    COLOR_HUD_AMBER = theme.AMBER
    COLOR_GRID = theme.AMBER_FAINT
    COLOR_GRID_TEXT = theme.AMBER_DIM

    # DFS Colors
    COLOR_DFS_BG = theme.BG_SENSOR
    COLOR_DFS_BORDER = theme.AMBER
    COLOR_DFS_INSET = theme.AMBER_DIM
    COLOR_DFS_AMBER = theme.AMBER_BRIGHT
    COLOR_DFS_ORANGE = theme.AMBER_DIM
    COLOR_DFS_GREEN = theme.GREEN
    COLOR_DFS_DATA = theme.GREEN
    COLOR_DFS_WHITE = theme.GREEN_BRIGHT
    COLOR_DFS_GRAY = theme.GREY
    COLOR_DFS_RED = theme.RED
    COLOR_DFS_YELLOW = theme.GREEN_BRIGHT

    # Laser/Targeting Colors
    COLOR_LASER_ACTIVE = theme.GREEN          # your beam is a sensor
    COLOR_LASER_PAINTED = theme.AMBER_BRIGHT  # ...that has something on it

    # Threat/Warning Colors
    COLOR_THREAT_RED = theme.RED
    COLOR_THREAT_DIM = theme.RED_DIM
    COLOR_MISSILE_VECTOR = theme.RED_BRIGHT
    COLOR_MISSILE_LOCK = theme.RED

    # Corridor Display
    COLOR_CORRIDOR_BRIGHT = theme.GREEN
    COLOR_CORRIDOR_DIM = theme.GREEN_DIM
    COLOR_CORRIDOR_FILL = (*theme.GREEN, 18)
    COLOR_CORRIDOR_RADAR = (*theme.GREEN, 30)

    # Font Sizes
    FONT_SIZE_LARGE = 35
    FONT_SIZE_BODY = 28
    FONT_SIZE_RADAR = 25
    FONT_SIZE_SCAN_HEADER = 32
    FONT_SIZE_SCAN_BODY = 24
    FONT_SIZE_GRID = 18
    FONT_SIZE_TINY = 20

    # Blink Configuration
    LOCK_BLINK_FREQUENCY = 10
    LOCK_BORDER_WIDTH = 10

    # endregion

    def __init__(self, screen):
        self.screen = screen
        self.lock_blink_counter = 0
        self.readouts = TopPanelReadouts()
        self.buttons = ButtonLayer()
        self._telemetry_rect = None

        # Initialize all fonts at once
        self.font_large = fonts.legacy_font(self.FONT_SIZE_LARGE)
        self.font_body = fonts.legacy_font(self.FONT_SIZE_BODY)
        self.font_radar_label = fonts.legacy_font(self.FONT_SIZE_RADAR)
        self.font_scan_header = fonts.legacy_font(self.FONT_SIZE_SCAN_HEADER)
        self.font_scan_body = fonts.legacy_font(self.FONT_SIZE_SCAN_BODY)
        self.font_grid = fonts.legacy_font(self.FONT_SIZE_GRID)
        self.font_tiny = fonts.legacy_font(self.FONT_SIZE_TINY)

        # Console screens (menus, lobby)
        self.menu_title_font = fonts.font(56)
        self.menu_font = fonts.font(28)
        self.menu_small_font = fonts.font(18)
        self.menu_key_font = fonts.font(14)

    #Menu stuff

    def draw_text_screen(self, title, lines, footer="", header="", buttons=()):
        """A framed console, same style as the in-game operator console: header
        strip, title, readout lines, a column of buttons
        [(label, key hint, action) or (label, key hint, action, enabled)],
        and a fault line (`footer`) or the input prompt along the bottom."""
        self.screen.fill(theme.BLACK)
        self.buttons.begin_frame()
        w, h = self.screen.get_size()

        small = self.menu_small_font
        title_surf = self.menu_title_font.render(title, True, theme.AMBER_BRIGHT)
        line_surfs = [self.menu_font.render(line, True, theme.GREEN) for line in lines]
        footer_surf = small.render(footer, True, theme.RED) if footer else None

        btn_w, btn_h, btn_gap = 360, 50, 12

        # Plain fields on black, like the mission log: no card, one left margin
        x0 = 40
        top = 32
        header_surf = small.render(header.upper(), True, theme.AMBER_DIM)
        self.screen.blit(header_surf, (x0, top))
        rule_y = top + header_surf.get_height() + 10
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (x0, rule_y), (w - x0, rule_y))

        y = rule_y + 40
        self.screen.blit(title_surf, title_surf.get_rect(topleft=(x0, y)))
        y += title_surf.get_height() + 36
        for surf in line_surfs:
            self.screen.blit(surf, surf.get_rect(topleft=(x0, y)))
            y += surf.get_height() + 12
        if lines and buttons:
            y += 24
        for label, key, action, *rest in buttons:
            enabled = rest[0] if rest else True
            rect = pygame.Rect(x0, y, btn_w, btn_h)
            draw_button(self.screen, rect, label, key=key, enabled=enabled, align="left",
                        font=self.menu_font, key_font=self.menu_key_font)
            self.buttons.register(rect, action, enabled=enabled)
            y += btn_h + btn_gap

        # Bottom line: the last fault if there is one, else the input prompt
        if footer_surf is None:
            footer_surf = small.render(f"STATUS: AWAITING INPUT {blink_cursor()}", True, theme.AMBER_DIM)
        self.screen.blit(footer_surf, footer_surf.get_rect(bottomleft=(x0, h - 32)))

        self.buttons.end_frame()
        end_blit()

    def draw_debrief_screen(self, status, detail, action, label):
        """End-of-mission readout: plain left-aligned fields on black, no frame or
        ornament. The one action is an underlined text line that is its own click area."""
        from datetime import datetime, timezone

        self.screen.fill(theme.BLACK)
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        x0 = 40
        head = self.menu_small_font
        body = self.menu_font

        top = 32
        self.screen.blit(head.render("ERGOT SYSTEMS // MISSION LOG", True, theme.AMBER_DIM), (x0, top))
        utc = head.render(f"UTC {datetime.now(timezone.utc).strftime('%H:%M:%S')}", True, theme.AMBER_DIM)
        self.screen.blit(utc, utc.get_rect(topright=(w - x0, top)))
        rule_y = top + head.get_height() + 10
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (x0, rule_y), (w - x0, rule_y))

        line_h = body.get_height() + 10
        label_w = body.size("STATUS  ")[0]
        y = rule_y + 24
        for name, value, color in (("STATUS", status, theme.AMBER_BRIGHT), ("DETAIL", detail, theme.GREEN)):
            self.screen.blit(body.render(name, True, theme.AMBER_DIM), (x0, y))
            self.screen.blit(body.render(value, True, color), (x0 + label_w, y))
            y += line_h

        # The one action, bottom-left, as plain text with an underline
        text = body.render(label, True, theme.AMBER)
        key = head.render("  [ENTER]", True, theme.AMBER_DIM)
        y = h - 48
        self.screen.blit(text, (x0, y))
        self.screen.blit(key, key.get_rect(bottomleft=(x0 + text.get_width(), y + text.get_height())))
        underline_y = y + text.get_height() + 2
        pygame.draw.line(self.screen, theme.AMBER_DIM, (x0, underline_y), (x0 + text.get_width() + key.get_width(), underline_y))
        click = pygame.Rect(x0 - 8, y - 6, text.get_width() + key.get_width() + 16, text.get_height() + 12)
        self.buttons.register(click, action)

        self.buttons.end_frame()
        end_blit()

    def draw_splash_screen(self, enabled: bool, timer: float):
        """Boot screen in the operator-console style: a small system identification
        strip, labelled sections with left-aligned fields, a scrolling boot log with
        status words, and a load block that states progress as numbers and text."""
        if not enabled:
            return

        import re
        from datetime import datetime, timezone

        w, h = self.screen.get_size()
        flicker = 0.96 + math.sin(timer * 35.0) * 0.02

        def lit(col):
            return tuple(int(v * flicker) for v in col)

        FRAME = theme.AMBER
        TITLE = lit(theme.AMBER_BRIGHT)
        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        LOG = lit(theme.GREEN)
        LOG_HOT = lit(theme.GREEN_BRIGHT)
        FAULT = lit(theme.RED_BRIGHT)

        ident_font = fonts.font(17)
        field_font = fonts.font(19)
        boot_font = fonts.font(19)
        status_font = fonts.font(17)

        self.screen.fill(theme.BLACK)

        pw = min(w - 48, 900)
        ph = min(h - 48, 780)
        panel = pygame.Rect(0, 0, pw, ph)
        panel.center = (w // 2, h // 2)
        self._frame(panel, FRAME, fill=theme.BG, tick=14, width=2)

        x0, x1 = panel.left + 24, panel.right - 24
        utc = datetime.now(timezone.utc).strftime("%H:%M:%S")

        # ------------------------------------------------------------------
        # System identification strip (small: operational data comes first)
        # ------------------------------------------------------------------
        y = self._ident_strip(panel, x0, x1, ident_font, HEAD, RULE)

        # ------------------------------------------------------------------
        # System identification: fixed two-column field grid
        # ------------------------------------------------------------------
        line_h = field_font.get_height() + 6
        id_box = pygame.Rect(x0, y, x1 - x0, 3 * line_h + 40 + self.BOX_HEAD)
        self._section(id_box, "SYSTEM IDENTIFICATION")
        fields = [
            [("UNIT ID", "ITD-218562B"), ("DEBUG REF", "218562B")],
            [("FIRMWARE", "4.7.2"), ("BUILD", "2026.11.21")],
            [("MISSION", "SEEK AND DESTROY"), ("UTC", utc)],
        ]
        col_w = (x1 - x0) // 2
        for r, row in enumerate(fields):
            for c, (label, value) in enumerate(row):
                fx = x0 + 22 + c * col_w
                fy = id_box.top + 22 + self.BOX_HEAD + r * line_h
                self.screen.blit(field_font.render(label, True, HEAD), (fx, fy))
                self.screen.blit(field_font.render(value, True, LOG), (fx + 150, fy))
        y = id_box.bottom + 14

        # ------------------------------------------------------------------
        # Load block, pinned to the bottom of the frame
        # ------------------------------------------------------------------
        load_h = 104 + self.BOX_HEAD
        load_box = pygame.Rect(x0, panel.bottom - 18 - load_h, x1 - x0, load_h)

        # ------------------------------------------------------------------
        # Boot log: label, dotted leader, status column. Scrolls like a terminal.
        # ------------------------------------------------------------------
        lines = [
            "INITIALIZING MEMORY.........................OK",
            "CHECKING ECC MEMORY BANKS...................OK",
            "VERIFYING FIRMWARE CRC......................OK",
            "STARTING SENSOR SUBSYSTEM...................OK",
            "INITIALIZING INERTIAL GUIDANCE..............OK",
            "LINKING DEEP SPACE TELEMETRY................OK",
            "ESTABLISHING QUANTUM RELAY..................FAILED",
            "VERIFYING NAVIGATION DATABASE...............OK",
            "LOADING STELLAR CATALOG.....................OK",
            "UPDATING EPHEMERIS CACHE....................OK",
            "CHECKING REACTION CONTROL THRUSTERS.........OK",
            "INITIALIZING REACTOR CONTROL................OK",
            "REACTOR OUTPUT..............................98.7%",
            "SCANNING EXTERNAL HARDPOINTS................OK",
            "BOOTING FLIGHT COMPUTER.....................OK",
            "LOADING TARGETING MATRICES..................OK",
            "INITIALIZING THREAT ANALYSIS................OK",
            "ARMOR STATUS................................NOMINAL",
            "LONG RANGE ARRAY............................ONLINE",
            "PASSIVE RADAR...............................ONLINE",
            "COMMUNICATIONS ARRAY........................ONLINE",
            "DISTRESS RECEIVER...........................STANDBY",
            "ENCRYPTION KEYS.............................VALID",
            "AUTHENTICATING COMMAND AUTHORITY............OK",
            "MISSION PROFILE.............................SEEK AND DESTROY",
            f"UTC TIME....................................{utc}",
            "DEBUG MONITOR: REF 218562B",
            "SYSTEM READY.",
        ]

        boot_start = 1.1
        line_delay = 0.48

        log_box = pygame.Rect(x0, y, x1 - x0, load_box.top - 14 - y)
        self._section(log_box, f"BOOT LOG  //  {len(lines)} ENTRIES")

        boot_lh = boot_font.get_height() + 4
        log_top = log_box.top + 28 + self.BOX_HEAD
        log_left = log_box.left + 22
        log_right = log_box.right - 22
        status_x = log_left + int((log_right - log_left) * 0.64)
        visible = max(1, (log_box.bottom - 12 - log_top) // boot_lh)

        started = [i for i in range(len(lines)) if timer > boot_start + i * line_delay]
        if started:
            last = started[-1]
            first = max(0, last - visible + 1)
            for row, i in enumerate(range(first, last + 1)):
                text = lines[i]
                chars = min(len(text), int((timer - (boot_start + i * line_delay)) * 42))
                y0 = log_top + row * boot_lh
                m = re.match(r"^(.*?)\.{3,}\s*(.*)$", text)

                if m is None:
                    color = TITLE if text.startswith("SYSTEM READY") else LOG
                    surf = boot_font.render(text[:chars], True, color)
                    self.screen.blit(surf, (log_left, y0))
                    cursor_x = log_left + surf.get_width()
                else:
                    label, status = m.group(1), m.group(2)
                    status_start = m.start(2)

                    lab = boot_font.render(label[:chars], True, LOG)
                    self.screen.blit(lab, (log_left, y0))
                    cursor_x = log_left + lab.get_width()

                    if chars >= len(label):
                        label_end = log_left + boot_font.size(label)[0] + 10
                        for gx in range(label_end, status_x - 10, 9):
                            pygame.draw.rect(self.screen, theme.AMBER_DIM, (gx, y0 + boot_lh - 9, 2, 2))
                        cursor_x = status_x

                    if chars > status_start:
                        word = status.upper()
                        if "FAIL" in word:
                            color = FAULT
                        elif "STANDBY" in word or "SEEK" in word:
                            color = TITLE
                        else:
                            color = LOG_HOT
                        st = boot_font.render(status[:chars - status_start], True, color)
                        self.screen.blit(st, (status_x, y0))
                        cursor_x = status_x + st.get_width()

                if i == last:
                    cur = boot_font.render(blink_cursor(), True, LOG_HOT)
                    self.screen.blit(cur, (cursor_x + 2, y0))

        # ------------------------------------------------------------------
        # Load block: bar, numeric readout, explicit status text
        # ------------------------------------------------------------------
        self._section(load_box, "LOAD SEQUENCE")

        total = len(lines) * line_delay
        frac = min(1.0, max(0.0, (timer - boot_start) / total))
        faults = sum(1 for i in started if "FAILED" in lines[i])
        entries_done = len(started)

        bar = pygame.Rect(load_box.left + 22, load_box.top + 24 + self.BOX_HEAD, load_box.width - 44, 10)
        pygame.draw.rect(self.screen, theme.GREEN_FAINT, bar)
        pygame.draw.rect(self.screen, LOG, (bar.left, bar.top, int(bar.width * frac), bar.height))
        pygame.draw.rect(self.screen, HEAD, bar, 1)

        def blit_seq(x, y, parts):
            for text, color in parts:
                surf = status_font.render(text, True, color)
                self.screen.blit(surf, (x, y))
                x += surf.get_width()

        row_a = bar.bottom + 12
        blit_seq(load_box.left + 22, row_a, [
            (f"LOAD {int(frac * 100):3d}%", LOG),
            (f"   ENTRIES {entries_done:02d}/{len(lines):02d}", HEAD),
            (f"   FAULTS {faults:02d}", FAULT if faults else HEAD),
        ])

        if timer < boot_start:
            status_text, status_color = "STATUS: INITIALIZING", HEAD
        elif frac < 1.0:
            status_text, status_color = "STATUS: BOOTING", LOG
        elif faults:
            status_text, status_color = f"STATUS: READY, {faults} FAULT{'S' if faults != 1 else ''}", FAULT
        else:
            status_text, status_color = "STATUS: READY", TITLE

        row_b = row_a + status_font.get_height() + 8
        blit_seq(load_box.left + 22, row_b, [(status_text, status_color)])

        if timer > 4.2 and int(timer * 2.5) % 2 == 0:
            msg = status_font.render("PRESS ENTER TO CONTINUE", True, TITLE)
            self.screen.blit(msg, msg.get_rect(topright=(load_box.right - 22, row_b)))
        else:
            msg = status_font.render("INPUT: LOCKED", True, HEAD)
            self.screen.blit(msg, msg.get_rect(topright=(load_box.right - 22, row_b)))

    # Identification strip text, shared by the boot screen and the main menu
    IDENT_LINE = "ERGOT SYSTEMS // INTERSTELLAR COMPUTING DIVISION"
    REV_LINE = "REV 4.7.2  BUILD 2026.11.21"

    # Room a box's heading line takes up inside it, above its contents
    BOX_HEAD = 8

    def _box_title(self, rect, title, color=theme.AMBER, steady=False):
        """A box's name as a heading line inside its top-left corner (never cut into the border)."""
        font = fonts.font(15)
        surf = (font.render_steady if steady else font.render)(title, True, color)
        self.screen.blit(surf, (rect.left + 22, rect.top + 6))

    def _section(self, rect, title, frame=theme.AMBER_DIM, text=theme.AMBER):
        """Framed section with its name as a heading line inside the top."""
        self._frame(rect, frame, fill=None, tick=8)
        self._box_title(rect, title, text)

    def _ident_strip(self, panel, x0, x1, font, color, rule_color):
        """Identification line over a rule across the top of a panel. Returns the y below it."""
        y = panel.top + 18
        ident = font.render(self.IDENT_LINE, True, color)
        self.screen.blit(ident, (x0, y))
        rev = font.render(self.REV_LINE, True, color)
        self.screen.blit(rev, rev.get_rect(topright=(x1, y)))
        y += ident.get_height() + 8
        pygame.draw.line(self.screen, rule_color, (x0, y), (x1, y))
        return y + 16

    def draw_main_menu(self, title, callsign, buttons, footer=""):
        """The main menu, laid out like the boot screen: identification strip, a
        title, a pilot-record field grid, a framed command grid, and a status
        block along the bottom. `buttons` is [(label, key hint, action)]; each is
        registered in the same call that draws it."""
        from datetime import datetime, timezone

        self.screen.fill(theme.BLACK)
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        flicker = 0.96 + math.sin(pygame.time.get_ticks() / 1000.0 * 35.0) * 0.02

        def lit(col):
            return tuple(int(v * flicker) for v in col)

        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        TITLE = lit(theme.AMBER_BRIGHT)
        LOG = lit(theme.GREEN)
        FAULT = lit(theme.RED_BRIGHT)

        field_font = fonts.font(19)
        status_font = fonts.font(17)
        btn_font = fonts.font(19)
        key_font = fonts.font(14)

        pw = min(w - 48, 900)
        ph = min(h - 48, 780)
        panel = pygame.Rect(0, 0, pw, ph)
        panel.center = (w // 2, h // 2)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)
        x0, x1 = panel.left + 24, panel.right - 24

        y = self._ident_strip(panel, x0, x1, fonts.font(17), HEAD, RULE)

        # Title
        title_surf = fonts.font(40).render(title, True, TITLE)
        self.screen.blit(title_surf, (x0, y))
        y += title_surf.get_height() + 14

        # Pilot record: two-column field grid, same as the boot identification block
        line_h = field_font.get_height() + 6
        record = pygame.Rect(x0, y, x1 - x0, 2 * line_h + 40 + self.BOX_HEAD)
        self._section(record, "PILOT RECORD")
        utc = datetime.now(timezone.utc).strftime("%H:%M:%S")
        fields = [
            [("CALLSIGN", callsign or "-"), ("UNIT ID", "ITD-218562B")],
            [("MISSION", "SEEK AND DESTROY"), ("UTC", utc)],
        ]
        col_w = (x1 - x0) // 2
        for r, row in enumerate(fields):
            for c, (label, value) in enumerate(row):
                fx = x0 + 22 + c * col_w
                fy = record.top + 22 + self.BOX_HEAD + r * line_h
                self.screen.blit(field_font.render(label, True, HEAD), (fx, fy))
                self.screen.blit(field_font.render(value, True, LOG), (fx + 150, fy))
        y = record.bottom + 14

        # Status block pinned to the bottom of the frame
        status_h = 96 + self.BOX_HEAD
        status_box = pygame.Rect(x0, panel.bottom - 18 - status_h, x1 - x0, status_h)

        # Command grid fills the space between the record and the status block
        command = pygame.Rect(x0, y, x1 - x0, status_box.top - 14 - y)
        self._section(command, "COMMAND")
        btn_h, btn_gap, pad = 46, 12, 22
        grid_h = len(buttons) * btn_h + (len(buttons) - 1) * btn_gap
        top = command.top + (command.height - grid_h) // 2
        for i, (label, key, action) in enumerate(buttons):
            rect = pygame.Rect(command.left + pad, top + i * (btn_h + btn_gap), command.width - 2 * pad, btn_h)
            self.buttons.button(self.screen, rect, label, action, key=key, align="left",
                                font=btn_font, key_font=key_font)

        self._section(status_box, "STATUS", HEAD, theme.AMBER)
        row_a = status_box.top + 30 + self.BOX_HEAD
        if footer:
            status_text, status_color = footer, FAULT
        else:
            status_text, status_color = f"STATUS: AWAITING INPUT {blink_cursor()}", TITLE
        self.screen.blit(status_font.render(status_text, True, status_color), (status_box.left + 22, row_a))
        hint = status_font.render("SELECT BY KEY OR CLICK", True, HEAD)
        self.screen.blit(hint, hint.get_rect(topright=(status_box.right - 22, row_a)))

        self.buttons.end_frame()
        end_blit()

    def _get_world_bounds(self):
        """Calculate world viewport bounds from screen dimensions.

        Returns:
            tuple: (world_left, world_right, world_top, world_bottom)
        """
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        return (
            self.PANEL_WIDTH,
            screen_width - self.PANEL_WIDTH,
            self.THIN_HEIGHT,
            screen_height - self.THIN_HEIGHT,
        )

    def _get_panel_rects(self):
        """The four console panels around the viewport: (top, bottom, left, right)."""
        w, h = self.screen.get_size()
        return (
            pygame.Rect(0, 0, w, self.THIN_HEIGHT),
            pygame.Rect(0, h - self.THIN_HEIGHT, w, self.THIN_HEIGHT),
            pygame.Rect(0, self.THIN_HEIGHT, self.PANEL_WIDTH, h - 2 * self.THIN_HEIGHT),
            pygame.Rect(w - self.PANEL_WIDTH, self.THIN_HEIGHT, self.PANEL_WIDTH, h - 2 * self.THIN_HEIGHT),
        )

    def _frame(self, rect, color=theme.AMBER, fill=theme.BG, tick=10, width=1):
        """The one instrument-box style (see draw_frame in asset_handlers/buttons.py)."""
        draw_frame(self.screen, rect, color, fill, tick=tick, width=width)

    def _button(self, rect, label, action, key=None, lit=None, enabled=True, hold=False, **style):
        """Draw a console button and make it clickable (see ButtonLayer.button)."""
        self.buttons.button(self.screen, rect, label, action, key=key, lit=lit, enabled=enabled, hold=hold, **style)

    def _button_row(self, rect, specs, gap=8):
        """Lay buttons out left to right across `rect` (see ButtonLayer.button_row)."""
        self.buttons.button_row(self.screen, rect, specs, gap=gap)

    def _bank(self, rect, title, specs, cols):
        """A framed bank of buttons in a grid. specs: (label, action, kwargs) per button."""
        rect = pygame.Rect(rect)
        self._frame(rect, theme.AMBER_DIM, tick=8)
        self._box_title(rect, title, steady=True)

        pad, gap = 14, 8
        head = 24
        rows = (len(specs) + cols - 1) // cols
        inner = pygame.Rect(rect.left + pad, rect.top + head, rect.width - 2 * pad, rect.height - head - pad)
        bw = (inner.width - gap * (cols - 1)) // cols
        bh = min(52, (inner.height - gap * (rows - 1)) // rows)
        top = inner.top + (inner.height - (bh * rows + gap * (rows - 1))) // 2
        for i, (label, action, kwargs) in enumerate(specs):
            r, c = divmod(i, cols)
            self._button((inner.left + c * (bw + gap), top + r * (bh + gap), bw, bh), label, action, **kwargs)

    def draw_control_banks(self, ship, cockpit, map_open=False, blink_busy=False,
                           sensor_buttons=()):
        """Two banks of switches in the bottom panel, either side of ship telemetry.

        Only the controls that don't belong to an instrument live here; the laser,
        DFS and radar have their buttons on their own panels.
        """
        tele = self._telemetry_rect
        if tele is None:
            return
        w = self.screen.get_width()
        margin = 24
        bank_w = min(self.PANEL_WIDTH - 140, tele.left - 2 * margin)
        if bank_w < 150:
            return  # screen too narrow for the banks; the keys still work
        cols = 2 if bank_w >= 300 else 1

        has_target = getattr(cockpit.target, 'net_id', None) is not None
        can_fire = ship.can_fire() and has_target
        helm = [
            (f"FIRE MSL {ship.total_missiles:02d}", 'fire_missile',
             dict(key="P", lit=cockpit.has_missile_solution, enabled=can_fire, lit_color=theme.AMBER_BRIGHT,
                  states=("LOCK", "----"))),
            ("DECOY", 'decoy', dict(key="R-ALT")),
            ("BLINK", 'blink', dict(key="T", lit=blink_busy, enabled=not blink_busy, lit_color=theme.AMBER_BRIGHT,
                                    states=("BUSY", "RDY"))),
            ("INERT DAMP", 'toggle_dampening', dict(key="G", lit=ship.dampening)),
        ]
        displays = [
            *sensor_buttons,
            ("TAC MAP", 'toggle_map', dict(key="M", lit=map_open)),
            ("CONSOLE", 'open_console', dict(key="ESC")),
        ]
        left = pygame.Rect(margin, tele.top, bank_w, tele.height)
        right = pygame.Rect(w - margin - bank_w, tele.top, bank_w, tele.height)
        self._bank(left, "HELM // WEAPONS", helm, cols)
        self._bank(right, "SENSORS // DISPLAYS", displays, cols)

    def _get_radar_bounds(self):
        """Calculate radar panel bounds and return geometry.

        Returns:
            tuple: (radar_x, radar_y, radar_size)
        """
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        radar_x = screen_width - self.PANEL_WIDTH + self.RADAR_PADDING
        radar_y = self.THIN_HEIGHT + self.RADAR_PADDING
        radar_size = screen_height - 2 * self.THIN_HEIGHT - 2 * self.RADAR_PADDING
        # Leave room underneath for the laser target box and its buttons (14px gap + 70px box)
        radar_size = min(radar_size - 84, self.PANEL_WIDTH - 2 * self.RADAR_PADDING)

        return radar_x, radar_y, radar_size

    def draw_ship_info(self, ship, cockpit, instrument_lines=()):
        """Ship telemetry: three columns of readouts in the bottom panel, under the viewport.

        Column widths come from the text they hold, so nothing overlaps whatever
        the numbers are; the box grows to fit and stays centred under the viewport.
        """
        font = fonts.font(19)
        line_h = font.get_height() + 3

        LIVE = theme.GREEN          # live readouts / system on
        CAUTION = theme.AMBER_BRIGHT
        THREAT = theme.RED
        LABEL = theme.AMBER_DIM     # headings and switched-off systems

        def on(flag):
            return LIVE if flag else LABEL

        # --- Column 1: nav ---
        nav = [
            ("NAV-COM", LABEL),
            (f"POS  X {int(ship.pos_x):+06d}  Y {int(ship.pos_y):+06d}", LIVE),
            (f"GRID {self.grid_ref(ship.pos_x, ship.pos_y)}", LIVE),
            (f"VEL  X {ship.dir_x:+05.1f}  Y {ship.dir_y:+05.1f}", LIVE),
            (f"SPD  {ship.speed:03.0f} / {SHIP_MAX_SPEED:03d} U", LIVE),
            (f"HDG  {int(ship.heading) % 360:03d} DEG", LIVE),
        ]

        # --- Column 2: subsystems (value in brackets drives the colour) ---
        damp = getattr(ship, "dampening", True)
        braking = getattr(ship, "braking", False)
        subsystems = [
            ("SUBSYSTEMS", LABEL),
            (f"INERT DAMP  [{'ON' if damp else 'OFF'}]", on(damp)),
            (f"BRAKE       [{'ON' if braking else 'OFF'}]", on(braking)),
            *[(text, on(is_on)) for text, is_on in instrument_lines],
        ]

        # --- Column 3: tactical ---
        if ship.missile_cooling_down:
            msl = (f"MSL  {ship.total_missiles:02d}/{TOTAL_MISSILES:02d}  RCHG {ship.missile_cooldown_timer:.1f}S", CAUTION)
        else:
            msl = (f"MSL  {ship.total_missiles:02d}/{TOTAL_MISSILES:02d}  READY", LIVE)
        health = int(getattr(ship, "health", 100))
        hull_col = THREAT if health < 20 else (CAUTION if health < 40 else LIVE)
        if ship.painted or cockpit.enemy_has_missile_solution:
            threat = ("THREAT  LOCK ON YOU" if cockpit.enemy_has_missile_solution else "THREAT  RADAR PAINTED", THREAT)
        elif cockpit.has_missile_solution:
            threat = ("TGT   LOCK ACQUIRED", CAUTION)
        else:
            threat = ("THREAT  NONE", LABEL)
        tactical = [("TACTICAL", LABEL), threat, msl, (f"HULL  {health:03d}/100", hull_col)]

        columns = [nav, subsystems, tactical]
        rendered = [[font.render(t, True, c) for t, c in col] for col in columns]
        col_w = [max(s.get_width() for s in col) for col in rendered]

        pad, gap = 22, 44
        box_w = sum(col_w) + gap * (len(columns) - 1) + pad * 2
        box_h = self.THIN_HEIGHT - 24
        world_left, world_right, _, world_bottom = self._get_world_bounds()
        box = pygame.Rect(0, 0, box_w, box_h)
        box.midtop = ((world_left + world_right) // 2, world_bottom + 12)
        self._telemetry_rect = box
        self._frame(box)

        rows = max(len(c) for c in columns)
        y0 = box.top + (box_h - rows * line_h) // 2 + 4
        x = box.left + pad
        for col, w in zip(rendered, col_w):
            for i, surf in enumerate(col):
                self.screen.blit(surf, (x, y0 + i * line_h))
            # Heading underline
            pygame.draw.line(self.screen, theme.AMBER_FAINT,
                             (x, y0 + line_h - 2), (x + w, y0 + line_h - 2))
            x += w + gap

    def draw_ui_layout(self):
        """Draw UI panel backgrounds and borders with clean CRT chassis framing."""
        screen_width, screen_height = self.screen.get_size()
        panels = self._get_panel_rects()

        # 1-3. Grimy, worn panel chassis (background and frame),
        # baked once per screen size in asset_handlers/grime.py
        key = (screen_width, screen_height)
        if getattr(self, "_panel_cache_key", None) != key:
            labels = ["PNL-A1  //  ACCESS 7C", "PNL-B4  //  NO STEP", "PNL-L2", "PNL-R2"]
            # Old burned-in readouts go in the bottom panel's empty wings either side
            # of ship telemetry (panel-local coords). Other panels are covered by instruments.
            ghost_w = self.PANEL_WIDTH - 140
            ghost_h = self.THIN_HEIGHT - 44
            ghosts = [
                (),
                ((24, 22, ghost_w, ghost_h), (screen_width - 24 - ghost_w, 22, ghost_w, ghost_h)),
                (),
                (),
            ]
            self._panel_cache = [
                build_panel(p.size, 1983 + i, labels[i], self.COLOR_BORDER_PRIMARY, ghosts[i])
                for i, p in enumerate(panels)
            ]
            self._panel_cache_key = key
        for panel, surf in zip(panels, self._panel_cache):
            self.screen.blit(surf, panel)

        # Background machine chatter in the top panel, either side of the callsign plate
        self.readouts.draw(self.screen, panels[0], exclude=self._callsign_rect())

    def _callsign_rect(self):
        """The pilot ID box: top-left of the top panel."""
        return pygame.Rect(24, 22, 380, self.THIN_HEIGHT - 44)

    def draw_callsign_plate(self, callsign, player_id, pilots_on_net, local):
        """Pilot ID readout: callsign, IFF code and link status, in the same
        framed-box style as ship telemetry."""
        rect = self._callsign_rect()
        LABEL = theme.AMBER_DIM
        LIVE = theme.GREEN

        self._frame(rect)
        self._box_title(rect, "PILOT ID")

        pad = 22
        x = rect.left + pad

        # Callsign: the one big thing in the box
        name = callsign or "UNREGISTERED"
        big = fonts.font(34)
        name_surf = big.render(name, True, theme.AMBER_BRIGHT)
        if name_surf.get_width() > rect.width - 2 * pad:
            name_surf = fonts.font(26).render(name, True, theme.AMBER_BRIGHT)
        name_y = rect.top + 8 + self.BOX_HEAD + 14
        self.screen.blit(name_surf, (x, name_y))

        rule_y = name_y + big.get_height() + 6
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (x, rule_y), (rect.right - pad, rule_y))

        # Two rows of label / value underneath
        iff = zlib.crc32(name.encode()) & 0xFFFFFF  # same callsign, same code
        if local:
            net_value, net_color = "LOCAL SIM", LABEL
        else:
            net_value = f"{pilots_on_net} {'PILOT' if pilots_on_net == 1 else 'PILOTS'} ON NET"
            net_color = LIVE
        rows = [
            ("IFF", f"{iff >> 12:03X}-{iff & 0xFFF:03X}", LIVE),
            ("NET", net_value, net_color),
        ]
        small = fonts.font(17)
        line_h = small.get_height() + 4
        value_x = x + small.size("IFF ")[0] + 14
        y = rule_y + 10
        for label, value, color in rows:
            self.screen.blit(small.render(label, True, LABEL), (x, y))
            self.screen.blit(small.render(value, True, color), (value_x, y))
            y += line_h

        # Slot number at the end of the IFF row, and a carrier lamp at the end of the NET row
        slot = small.render(f"SLOT {player_id:02d}", True, LABEL)
        self.screen.blit(slot, slot.get_rect(topright=(rect.right - pad, rule_y + 10)))
        if not local:
            lamp_on = (pygame.time.get_ticks() // 700) % 2 == 0
            lamp = (rect.right - pad - 4, rule_y + 10 + line_h + small.get_height() // 2)
            pygame.draw.circle(self.screen, LIVE if lamp_on else theme.GREEN_FAINT, lamp, 4)

    def draw_ui_ftl_override(self, ftl_jumping):
        """Draw simple FTL JUMPING text boxes that fade out.

        Args:
            ftl_jumping: Boolean indicating if FTL jump is active
        """
        if not ftl_jumping:
            return

        top_panel, bottom_panel, left_panel, right_panel = self._get_panel_rects()

        COLOR_PHOSPHOR = theme.GREEN
        COLOR_BLACK = theme.BLACK

        # Boot timer
        if not hasattr(self, 'ftl_boot_timer'):
            self.ftl_boot_timer = 0

        self.ftl_boot_timer += 1

        # Fade out
        opacity = max(0, 255 - (self.ftl_boot_timer * 2))

        if opacity <= 0:
            return

        # Font
        if not hasattr(self, 'font_crt'):
            self.font_crt = fonts.legacy_font(20)

        # Simple boxes with text in each panel
        panels = [
            (top_panel, "FTL JUMPING"),
            (bottom_panel, "FTL JUMPING"),
            (left_panel, "FTL\nJUMPING"),
            (right_panel, "FTL\nJUMPING"),
        ]

        for panel, text in panels:
            # Box
            box = pygame.Rect(
                panel.centerx - 60,
                panel.centery - 25,
                120,
                50
            )

            # Draw box
            surf = pygame.Surface(box.size, pygame.SRCALPHA)
            surf.fill((*COLOR_BLACK, opacity))
            pygame.draw.rect(surf, COLOR_PHOSPHOR, (0, 0, box.width, box.height), 2)

            # Draw text
            txt = self.font_crt.render(text, True, COLOR_PHOSPHOR)
            txt_x = (box.width - txt.get_width()) // 2
            txt_y = (box.height - txt.get_height()) // 2
            surf.blit(txt, (txt_x, txt_y))

            self.screen.blit(surf, box)

    def draw_world_grid(self, camera_x, camera_y, show_grid=True):
        """Draw coordinate grid overlay in world space.

        Args:
            camera_x: Camera X position
            camera_y: Camera Y position
            show_grid: Boolean to toggle grid on/off
        """
        if not show_grid:
            return

        screen_width, screen_height = self.screen.get_size()
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        grid_size = GRID_SIZE  # World units between grid lines

        # Calculate starting grid position in world space
        start_x = int(camera_x / grid_size) * grid_size
        start_y = int(camera_y / grid_size) * grid_size

        # Draw vertical grid lines
        x = start_x
        while x < camera_x + screen_width:
            screen_x = x - camera_x
            if world_left < screen_x < world_right:
                pygame.draw.line(
                    self.screen, self.COLOR_GRID,
                    (screen_x, world_top), (screen_x, world_bottom), 1
                )
                label = self.font_grid.render(str(int(x)), True, self.COLOR_GRID_TEXT)
                self.screen.blit(label, (screen_x + 5, world_top + 5))
            x += grid_size

        # Draw horizontal grid lines
        y = start_y
        while y < camera_y + screen_height:
            screen_y = y - camera_y
            if world_top < screen_y < world_bottom:
                pygame.draw.line(
                    self.screen, self.COLOR_GRID,
                    (world_left, screen_y), (world_right, screen_y), 1
                )
                label = self.font_grid.render(str(int(y)), True, self.COLOR_GRID_TEXT)
                self.screen.blit(label, (world_left + 5, screen_y + 5))
            y += grid_size

    def draw_missile_lock_warning(self, locked):
        """Draw red blinking border around viewport when missile lock detected."""
        if not locked:
            return

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        # Blink timing
        self.lock_blink_counter += 1
        if (self.lock_blink_counter // self.LOCK_BLINK_FREQUENCY) % 2 == 0:
            pygame.draw.rect(
                self.screen, self.COLOR_THREAT_RED,
                (world_left, world_top, world_right - world_left, world_bottom - world_top),
                self.LOCK_BORDER_WIDTH
            )

    def draw_laser_painted_warning(self, painted):
        """Draw flashing warning when ship is laser painted by enemy.

        Args:
            painted: Boolean indicating if ship is currently painted
        """
        if not painted:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        # Blink timing
        self.lock_blink_counter += 1
        blink_frequency = 8  # Faster than missile lock warning

        if (self.lock_blink_counter // blink_frequency) % 2 == 0:
            # Warning text in the bottom-right corner, clear of the gun-solution banner up top
            warning_text = self.font_body.render("LASER LOCK DETECTED", True, theme.RED_BRIGHT)
            self.screen.blit(warning_text, (world_right - warning_text.get_width() - 20,
                                            world_bottom - warning_text.get_height() - 20))

    def draw_radar(self, player_ship, signatures, is_scanning=False, sweep_angle=None):
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2

        # FIX: Max radius is half the bounding box, not the full bounding box
        max_radius = radar_size // 2

        # --- CRT Phosphor Background & Scanlines ---
        pygame.draw.rect(self.screen, theme.BG_SENSOR, radar_rect)  # Deep murky green background

        # Faux CRT scanlines
        for y in range(radar_y, radar_y + radar_size, 4):
            pygame.draw.line(self.screen, theme.GREEN_FAINT, (radar_x, y), (radar_x + radar_size, y))

        self._frame(radar_rect, self.COLOR_HUD_AMBER, fill=None, tick=15)

        # --- Tactical Grid ---
        # Hardware clip prevents edge blips or grid lines from ever drawing outside the radar box
        old_clip = self.screen.get_clip()
        self.screen.set_clip(radar_rect)

        grid_color = theme.GREEN_DIM  # Glowing dim green
        grid_spacing = max_radius // self.RADAR_GRID_COUNT

        # Axis Crosshairs
        pygame.draw.line(self.screen, grid_color, (radar_x, center_y), (radar_x + radar_size, center_y), 1)
        pygame.draw.line(self.screen, grid_color, (center_x, radar_y), (center_x, radar_y + radar_size), 1)

        # Distance Rings
        for i in range(1, self.RADAR_GRID_COUNT + 1):
            offset = grid_spacing * i
            pygame.draw.circle(self.screen, grid_color, (center_x, center_y), offset, 1)

        # Player position (Glowing cluster)
        pygame.draw.circle(self.screen, theme.WHITE, (center_x, center_y), 3)
        pygame.draw.rect(self.screen, theme.WHITE, (center_x - 1, center_y - 1, 3, 3))  # Hot core

        # --- Sweep arm: only while a scan is running (R), pointing at the ray being cast ---
        if sweep_angle is not None:
            arm_end = (center_x + math.cos(sweep_angle) * max_radius, center_y + math.sin(sweep_angle) * max_radius)
            pygame.draw.line(self.screen, theme.GREEN_BRIGHT, (center_x, center_y), arm_end, 1)

        # --- Plot Signatures ---
        radar_scale = max_radius / self.RADAR_SCALE
        player_x, player_y = player_ship.rect.center

        for sig_x, sig_y, color in signatures:
            rel_x = sig_x - player_x
            rel_y = sig_y - player_y

            radar_px = int(center_x + rel_x * radar_scale)
            radar_py = int(center_y + rel_y * radar_scale)

            # Blocky retro blips instead of smooth circles
            pygame.draw.rect(self.screen, color, (radar_px - 2, radar_py - 2, 4, 4))
            pygame.draw.rect(self.screen, tuple(min(255, c + 110) for c in color), (radar_px - 1, radar_py - 1, 2, 2))  # Hot center

        # Restore rendering area
        self.screen.set_clip(old_clip)

        # --- Blinking Retro Label ---
        show_label = True
        if is_scanning:
            # Blink every ~500ms
            show_label = (pygame.time.get_ticks() // 500) % 2 == 0

        if show_label:
            label_text = "RADAR [ SCANNING... ]" if is_scanning else "RADAR"
            label_color = self.COLOR_DATA if is_scanning else self.COLOR_HUD_AMBER
            label = self.font_radar_label.render(label_text, True, label_color)

            label_bg = pygame.Rect(radar_x + 12, radar_y + 12, label.get_width() + 16, label.get_height() + 6)
            pygame.draw.rect(self.screen, theme.BLACK, label_bg)  # Solid black background behind text
            pygame.draw.rect(self.screen, label_color, label_bg, 1)  # Thin neon border around text
            self.screen.blit(label, label.get_rect(center=label_bg.center))

    def draw_radar_controls(self, is_scanning):
        """SWEEP button in the scope's top-right corner. Drawn after the laser and
        DFS lines so they don't cross it."""
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        sweep = pygame.Rect(0, 0, 112, 34)
        sweep.topright = (radar_x + radar_size - 12, radar_y + 12)
        self._button(sweep, "SWEEP", 'radar_sweep', key="R", lit=is_scanning)

    def draw_laser(self, laser, laser_endpoint, camera_x, camera_y, active):
        if not active:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        radar_x, radar_y, radar_size = self._get_radar_bounds()

        origin_x, origin_y = laser.ship.rect.center
        end_x, end_y = laser_endpoint

        beam_color = self.COLOR_LASER_PAINTED if laser.painted else self.COLOR_LASER_ACTIVE

        # --- 1. World viewport beam ---
        viewport = pygame.Rect(
            world_left, world_top,
            world_right - world_left, world_bottom - world_top
        )
        self.screen.set_clip(viewport)

        screen_origin = (origin_x - camera_x, origin_y - camera_y)
        screen_end = (end_x - camera_x, end_y - camera_y)

        # Retro glowing laser effect: thick colored base with a hot white core
        pygame.draw.line(self.screen, beam_color, screen_origin, screen_end, 3)
        pygame.draw.line(self.screen, theme.WHITE, screen_origin, screen_end, 1)

        # Emitter box at the beam's origin, rotated to the beam direction so it
        # reads as the machine the beam comes out of (drawn over the beam start)
        rad = math.radians(laser.direction)
        fx, fy = math.cos(rad), math.sin(rad)     # along the beam
        px, py = -fy, fx                          # across the beam
        half_len, half_wid = 5, 4
        cx, cy = screen_origin
        emitter = [
            (cx + fx * half_len + px * half_wid, cy + fy * half_len + py * half_wid),
            (cx + fx * half_len - px * half_wid, cy + fy * half_len - py * half_wid),
            (cx - fx * half_len - px * half_wid, cy - fy * half_len - py * half_wid),
            (cx - fx * half_len + px * half_wid, cy - fy * half_len + py * half_wid),
        ]
        pygame.draw.polygon(self.screen, theme.BG, emitter)
        pygame.draw.polygon(self.screen, beam_color, emitter, 1)

        # Impact flare at the endpoint
        pygame.draw.circle(self.screen, theme.WHITE, screen_end, 2)
        pygame.draw.circle(self.screen, beam_color, screen_end, 4, 1)

        # Range readout beside the impact point while locked
        if laser.laser_locked:
            label = self.font_scan_body.render(f"RNG {laser.target_distance:.0f}", True, theme.AMBER_BRIGHT)
            label_rect = label.get_rect(midleft=(screen_end[0] + 14, screen_end[1] - 14))
            label_rect.clamp_ip(viewport)
            pygame.draw.rect(self.screen, theme.BG, label_rect.inflate(6, 2))
            self.screen.blit(label, label_rect)

        self.screen.set_clip(None)

        # --- 2. Radar panel beam ---
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2

        # FIX: Align scale calculation with the radar's max_radius correction
        max_radius = radar_size // 2
        radar_scale = max_radius / self.RADAR_SCALE

        rel_x = end_x - origin_x
        rel_y = end_y - origin_y
        radar_end_x = int(center_x + rel_x * radar_scale)
        radar_end_y = int(center_y + rel_y * radar_scale)

        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        self.screen.set_clip(radar_rect)

        # Sharp, thin vector line for the radar display
        pygame.draw.line(
            self.screen, beam_color,
            (center_x, center_y),
            (radar_end_x, radar_end_y),
            1
        )

        # Square phosphor impact blip on the radar
        pygame.draw.rect(self.screen, theme.WHITE, (radar_end_x - 1, radar_end_y - 1, 2, 2))

        self.screen.set_clip(None)

    def draw_laser_targeting_info(self, target_type: str, laser_assessor, enabled: bool):
        """Draw laser targeting assessment status below the radar panel.

        Args:
            target_type: String classification of the target
            laser_assessor: LaserAssessor object with lock info
            enabled: Boolean indicating if laser targeting is active
        """

        radar_x, radar_y, radar_size = self._get_radar_bounds()

        body = self.font_scan_body
        line_h = body.get_height() + 2

        # Box sits under the radar face, at half the height of the gap down to the bottom of the side panel
        box_x = radar_x
        box_y = radar_y + radar_size + 14
        box_w = radar_size
        box_h = (self.screen.get_height() - self.THIN_HEIGHT - 12 - box_y) // 2

        border_color = self.COLOR_HUD_AMBER if enabled else theme.AMBER_DIM
        self._frame((box_x, box_y, box_w, box_h), border_color, tick=8)

        # Title tab sitting on the top border
        header = self.font_tiny.render(" LASER TARGET ANALYSIS ", True, border_color)
        tab = header.get_rect(midleft=(box_x + 14, box_y))
        pygame.draw.rect(self.screen, theme.BG, tab)
        self.screen.blit(header, tab)

        # Box split in half: status on top, buttons below
        top_h = box_h // 2

        # The assessor reports "NOTHING"; the scene starts out with "Nothing"
        has_contact = target_type.upper() != "NOTHING"
        locked = laser_assessor.laser_locked

        # Controls on the right: sweep left/right (hold), lock, power
        # Buttons fill the bottom half of the box, edge to edge inside the frame
        controls = pygame.Rect(box_x + 8, box_y + top_h + 4, box_w - 16, box_h - top_h - 8)
        self._button_row(controls, [
            (1, "<", 'arrow_key_left', dict(key="", enabled=enabled, hold=True, align="center")),
            (1, ">", 'arrow_key_right', dict(key="", enabled=enabled, hold=True, align="center")),
            (2, "LOCK", 'laser_lock', dict(key="SPC", lit=locked, enabled=enabled and (locked or has_contact),
                                         lit_color=theme.AMBER_BRIGHT)),
            (2, "PWR", 'toggle_laser', dict(key="I", lit=enabled)),
        ], gap=6)

        # Status readouts: one row in the top half, as large as fits there
        if enabled:
            text_str1 = f"CLASS: {target_type.upper()}"
            color1 = self.COLOR_DATA if has_contact else theme.GREY
            if locked:
                text_str2, color2 = "STATUS: LOCK ACQUIRED", theme.AMBER_BRIGHT
            elif has_contact:
                text_str2, color2 = "STATUS: TRACKING", self.COLOR_HUD_AMBER
            else:
                text_str2, color2 = "STATUS: SEARCHING", theme.GREY
        else:
            text_str1, color1 = "TARGETING INACTIVE", theme.GREY  # switched off is not a threat
            text_str2, color2 = "SYSTEM OFFLINE", theme.GREY

        region_top = box_y + tab.height // 2 + 2
        region = pygame.Rect(box_x + 8, region_top, box_w - 16, box_y + top_h - 4 - region_top)
        gap = 28
        for size in (34, 30, 26, 22, 18, 14):
            status_font = fonts.font(size)
            surf1 = status_font.render(text_str1, True, color1)
            surf2 = status_font.render(text_str2, True, color2)
            if (status_font.get_height() <= region.height
                    and surf1.get_width() + gap + surf2.get_width() <= region.width):
                break
        y = region.centery - surf1.get_height() // 2
        self.screen.blit(surf1, (region.left + 8, y))
        self.screen.blit(surf2, (region.left + 8 + surf1.get_width() + gap, y))

    def draw_missile_vectors(self, player_id, missiles, camera_x, camera_y):
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        # Viewport center (reference origin for edge projection)
        center_x = (world_left + world_right) / 2
        center_y = (world_top + world_bottom) / 2

        enemy_missiles = [
            m for m in missiles
            if getattr(m.target, "net_id", None) == player_id
        ]

        for missile in enemy_missiles:
            # Convert missile position to screen space
            screen_x = missile.pos_x - camera_x
            screen_y = missile.pos_y - camera_y

            # Only draw edge indicators for off-screen threats
            if not (world_left < screen_x < world_right and world_top < screen_y < world_bottom):

                # Project Line of Sight to Viewport Edges
                rel_x = screen_x - center_x
                rel_y = screen_y - center_y

                if rel_x == 0 and rel_y == 0:
                    continue

                # Find intersection scale factor against the viewport box
                half_w = (world_right - world_left) / 2 - 15
                half_h = (world_bottom - world_top) / 2 - 15

                scale_x = abs(half_w / rel_x) if rel_x != 0 else float("inf")
                scale_y = abs(half_h / rel_y) if rel_y != 0 else float("inf")
                scale = min(scale_x, scale_y)

                # Edge anchor coordinates
                edge_x = center_x + rel_x * scale
                edge_y = center_y + rel_y * scale

                # Missile Velocity Vector Alignment
                vel_mag = math.hypot(missile.vel_x, missile.vel_y)
                if vel_mag > 0:
                    dir_x = missile.vel_x / vel_mag
                    dir_y = missile.vel_y / vel_mag
                else:
                    dir_x = -rel_x / math.hypot(rel_x, rel_y)
                    dir_y = -rel_y / math.hypot(rel_x, rel_y)

                # Vector Line Properties
                end_x = edge_x + dir_x * self.MISSILE_VECTOR_LENGTH
                end_y = edge_y + dir_y * self.MISSILE_VECTOR_LENGTH

                # Draw Main Trajectory Line
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_VECTOR,
                    (edge_x, edge_y), (end_x, end_y), 3
                )

                # Draw Vector Tip (Small crossbar to accent movement direction)
                perp_x = -dir_y * 4
                perp_y = dir_x * 4
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_VECTOR,
                    (end_x - perp_x, end_y - perp_y),
                    (end_x + perp_x, end_y + perp_y), 2
                )

    @staticmethod
    def grid_ref(x, y):
        """Grid cell containing a world position, as '<col>X <row>Y' (clamped to the world)."""
        col = min(max(int(x // GRID_SIZE), 0), WORLD_WIDTH // GRID_SIZE - 1)
        row = min(max(int(y // GRID_SIZE), 0), WORLD_HEIGHT // GRID_SIZE - 1)
        return f"{col}X {row}Y"

    MARKER_SHAPES = ("CIRCLE", "SQUARE", "TRIANGLE", "DIAMOND", "CROSS")

    @staticmethod
    def _draw_marker_shape(surface, shape, center, size, color):
        cx, cy = int(center[0]), int(center[1])
        if shape == "CIRCLE":
            pygame.draw.circle(surface, color, (cx, cy), size, 2)
        elif shape == "SQUARE":
            pygame.draw.rect(surface, color, (cx - size, cy - size, size * 2, size * 2), 2)
        elif shape == "TRIANGLE":
            pygame.draw.polygon(surface, color, [(cx, cy - size), (cx - size, cy + size), (cx + size, cy + size)], 2)
        elif shape == "DIAMOND":
            pygame.draw.polygon(surface, color, [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], 2)
        else:  # CROSS
            pygame.draw.line(surface, color, (cx - size, cy), (cx + size, cy), 2)
            pygame.draw.line(surface, color, (cx, cy - size), (cx, cy + size), 2)

    def map_screen_to_world(self, pos):
        """World position under a screen point on the tactical map (from the last drawn frame)."""
        center, scale, player_x, player_y = self._map_view
        return (player_x + (pos[0] - center[0]) / scale,
                player_y + (pos[1] - center[1]) / scale)

    def draw_tactical_map(self, active, player_ship, confirmed_contacts, scan_active=False, scan_range=1000, laser_active=False, laser_direction=0, laser_locked=False, locked_object=None, markers=(), marker_mode=None):
        """marker_mode: None, 'PICK' (choosing a shape) or a shape name (waiting for a click on the map)."""
        if not active:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        map_rect = pygame.Rect(
            self.PANEL_WIDTH,
            self.THIN_HEIGHT,
            screen_width - 2 * self.PANEL_WIDTH,
            screen_height - 2 * self.THIN_HEIGHT
        )

        pygame.draw.rect(self.screen, self.COLOR_DFS_BG, map_rect)

        previous_clip = self.screen.get_clip()
        self.screen.set_clip(map_rect)

        map_center = map_rect.center
        max_display_range = 5000

        # Centre on the same position the cockpit POS readout shows, so the
        # player dot sits exactly on its labelled coordinate.
        player_x, player_y = player_ship.pos_x, player_ship.pos_y
        scale = min(map_rect.width, map_rect.height) / (max_display_range * 2)

        def world_to_screen(wx, wy):
            """World coords (relative to player) to map panel pixels."""
            return map_center[0] + wx * scale, map_center[1] + wy * scale

        self._map_view = (map_center, scale, player_x, player_y)

        # Placing a marker: the whole map is the click target. Registered before
        # the other map buttons so they stay on top of it.
        if marker_mode in self.MARKER_SHAPES:
            self.buttons.register(map_rect, 'marker_place')

        # --- WORLD GRID (DIMMED) ---
        grid_color = theme.GREEN_FAINT
        view_margin = max_display_range * 1.5
        min_x = max(0, int((player_x - view_margin) // GRID_SIZE) * GRID_SIZE)
        max_x = min(WORLD_WIDTH, int((player_x + view_margin) // GRID_SIZE + 1) * GRID_SIZE)
        min_y = max(0, int((player_y - view_margin) // GRID_SIZE) * GRID_SIZE)
        max_y = min(WORLD_HEIGHT, int((player_y + view_margin) // GRID_SIZE + 1) * GRID_SIZE)

        for gx in range(min_x, max_x + 1, GRID_SIZE):
            p1 = world_to_screen(gx - player_x, min_y - player_y)
            p2 = world_to_screen(gx - player_x, max_y - player_y)
            pygame.draw.line(self.screen, grid_color, p1, p2, 1)

        for gy in range(min_y, max_y + 1, GRID_SIZE):
            p1 = world_to_screen(min_x - player_x, gy - player_y)
            p2 = world_to_screen(max_x - player_x, gy - player_y)
            pygame.draw.line(self.screen, grid_color, p1, p2, 1)

        # --- WORLD BOUNDARIES ---
        boundary_pts = [
            world_to_screen(0 - player_x, 0 - player_y),
            world_to_screen(WORLD_WIDTH - player_x, 0 - player_y),
            world_to_screen(WORLD_WIDTH - player_x, WORLD_HEIGHT - player_y),
            world_to_screen(0 - player_x, WORLD_HEIGHT - player_y)
        ]
        pygame.draw.polygon(self.screen, theme.AMBER_DIM, boundary_pts, 1)

        # --- CLOSE-RANGE SCAN RADIUS ---
        if scan_active:
            radius_px = scan_range * scale
            pygame.draw.circle(self.screen, (*theme.GREEN_FAINT, 40), map_center, int(radius_px))
            pygame.draw.circle(self.screen, (*theme.GREEN_DIM, 100), map_center, int(radius_px), 1)

        # --- LASER BEAM ---
        if laser_active:
            rad = math.radians(laser_direction - 90)
            beam_end_x = math.cos(rad) * LASER_RANGE
            beam_end_y = math.sin(rad) * LASER_RANGE

            beam_start = world_to_screen(0, 0)
            beam_end = world_to_screen(beam_end_x, beam_end_y)

            # Beam color changes if locked
            beam_color = theme.AMBER_BRIGHT if laser_locked else theme.GREEN
            pygame.draw.line(self.screen, beam_color, beam_start, beam_end, 2)

            # Highlight locked target with red circle
            if laser_locked and locked_object:
                obj_x = getattr(locked_object, 'pos_x', None) or locked_object.rect.center[0]
                obj_y = getattr(locked_object, 'pos_y', None) or locked_object.rect.center[1]
                lock_screen = world_to_screen(obj_x - player_x, obj_y - player_y)
                pygame.draw.circle(self.screen, theme.AMBER_BRIGHT, lock_screen, 12, 2)

        # --- CONFIRMED CONTACTS (With Confidence Fading) ---
        for pos_x, pos_y, contact_type, velocity, confidence in confirmed_contacts:
            screen_x, screen_y = world_to_screen(pos_x - player_x, pos_y - player_y)

            # Size and color scale with confidence
            marker_size = max(2, int(3 + confidence * 6))
            alpha = int(255 * confidence)
            color = self.COLOR_DFS_DATA
            drone_color = theme.GREEN_BRIGHT
            kind = contact_type.lower()

            pos = (int(screen_x), int(screen_y))

            # Create temporary surface for alpha blending
            marker_surface = pygame.Surface((marker_size * 3, marker_size * 3), pygame.SRCALPHA)
            marker_center = (marker_size + 1, marker_size + 1)

            # Contact symbol
            if kind == "asteroid":
                pygame.draw.polygon(marker_surface, (*color, alpha),
                                    [(marker_center[0], marker_center[1] - marker_size),
                                     (marker_center[0] - marker_size, marker_center[1] + marker_size),
                                     (marker_center[0] + marker_size, marker_center[1] + marker_size)])
            elif kind == "ship":
                pygame.draw.rect(marker_surface, (*color, alpha),
                                 (marker_center[0] - marker_size, marker_center[1] - marker_size,
                                  marker_size * 2, marker_size * 2))
            elif kind == "drone":
                pygame.draw.polygon(marker_surface, (*drone_color, alpha),
                                    [(marker_center[0] + marker_size, marker_center[1]),
                                     (marker_center[0] - marker_size // 2, marker_center[1] - marker_size),
                                     (marker_center[0] - marker_size // 2, marker_center[1] + marker_size)])
            else:
                pygame.draw.circle(marker_surface, (*color, alpha), marker_center, marker_size, 1)

            # Blit to screen
            self.screen.blit(marker_surface,
                             (pos[0] - marker_center[0], pos[1] - marker_center[1]))

            # Velocity vector (fades with confidence)
            vx, vy = velocity
            if (vx != 0 or vy != 0) and confidence > 0.1:
                vector_length = 25
                vel_mag = math.hypot(vx, vy)
                if vel_mag > 0:
                    dir_x = vx / vel_mag
                    dir_y = vy / vel_mag
                    head_x = int(screen_x + dir_x * vector_length)
                    head_y = int(screen_y + dir_y * vector_length)

                    # Draw vector with alpha
                    pygame.draw.line(self.screen, (*color, alpha), pos, (head_x, head_y), 1)

        # --- PLAYER MARKERS (local only) ---
        for i, (shape, mx, my) in enumerate(markers, 1):
            mpos = world_to_screen(mx - player_x, my - player_y)
            self._draw_marker_shape(self.screen, shape, mpos, 9, theme.AMBER_BRIGHT)
            tag = self.font_tiny.render(str(i), True, theme.AMBER_BRIGHT)
            self.screen.blit(tag, (mpos[0] + 12, mpos[1] - tag.get_height() // 2))

        # --- PLAYER CENTER ---
        pygame.draw.circle(self.screen, theme.WHITE, map_center, 5)

        # --- GRID COORDINATES ---
        # Cell indices (0X..nX across, 0Y..nY down), pinned to the panel edges so
        # they stay readable as the map scrolls. Kept clear of header/close button.
        label_top = map_rect.top + 56
        label_left = map_rect.left + 8
        for col in range(min_x // GRID_SIZE, max_x // GRID_SIZE):
            sx, _ = world_to_screen(col * GRID_SIZE + GRID_SIZE / 2 - player_x, 0)
            if map_rect.left + 40 < sx < map_rect.right - 10:
                txt = self.font_tiny.render(f"{col}X", True, self.COLOR_GRID_TEXT)
                self.screen.blit(txt, txt.get_rect(midtop=(int(sx), label_top)))
        for row in range(min_y // GRID_SIZE, max_y // GRID_SIZE):
            _, sy = world_to_screen(0, row * GRID_SIZE + GRID_SIZE / 2 - player_y)
            if label_top + 20 < sy < map_rect.bottom - 40:
                txt = self.font_tiny.render(f"{row}Y", True, self.COLOR_GRID_TEXT)
                self.screen.blit(txt, txt.get_rect(midleft=(label_left, int(sy))))

        self.screen.set_clip(previous_clip)
        # Frame last so contacts near the edge never draw over it
        self._frame(map_rect, self.COLOR_DFS_BORDER, fill=None, width=2, tick=14)

        # --- HEADER & FOOTER ---
        header = f"TACTICAL MAP  //  GRID {self.grid_ref(player_x, player_y)}"
        txt_header = self.font_scan_header.render(header, True, self.COLOR_DFS_AMBER)
        self.screen.blit(txt_header, (map_rect.x + 18, map_rect.y + 14))

        contact_count = len(confirmed_contacts)
        moving_count = sum(1 for c in confirmed_contacts if c[3][0] != 0 or c[3][1] != 0)
        avg_confidence = (sum(c[4] for c in confirmed_contacts) / contact_count * 100) if contact_count > 0 else 0

        footer = f"CONFIRMED: {contact_count}  MOVING: {moving_count}  SIGNAL: {int(avg_confidence)}%"
        txt_footer = self.font_scan_body.render(footer, True, self.COLOR_DFS_DATA)
        self.screen.blit(txt_footer, (map_rect.x + 18, map_rect.bottom - txt_footer.get_height() - 14))

        close = pygame.Rect(0, 0, 110, 34)
        close.topright = (map_rect.right - 14, map_rect.top + 14)
        self._button(close, "CLOSE", 'toggle_map', key="M")

        # --- MARKER CONTROLS (bottom right) ---
        if marker_mode in self.MARKER_SHAPES:
            prompt = self.font_scan_body.render(f"CLICK THE MAP TO PLACE {marker_mode}", True, self.COLOR_DFS_AMBER)
            self.screen.blit(prompt, prompt.get_rect(midbottom=(map_rect.centerx, map_rect.bottom - 14)))
        specs = []
        if marker_mode == 'PICK':
            specs = [(1, shape, f'marker_shape_{shape.lower()}', {}) for shape in self.MARKER_SHAPES]
            specs.append((1, "CANCEL", 'marker_cancel', {}))
        elif marker_mode in self.MARKER_SHAPES:
            specs = [(1, "CANCEL", 'marker_cancel', {})]
        else:
            specs = [(2, "ADD MARKER", 'marker_add', {}),
                     (2, "CLEAR MARKERS", 'marker_clear', dict(enabled=bool(markers)))]
        n = len(specs)
        row = pygame.Rect(0, 0, 130 * n + 8 * (n - 1) + (40 if marker_mode is None else 0), 34)
        row.bottomright = (map_rect.right - 14, map_rect.bottom - 14)
        self._button_row(row, specs)

    def draw_catastrophe_warning(self, active):
        """Draw subtle catastrophe alert - pulsing red border and corner X.

        Args:
            active: Boolean indicating if catastrophe warning is active
        """
        if not active:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        # Slower pulse (more subtle)
        self.lock_blink_counter += 1
        strobe_frequency = 12  # Slower, less jarring

        if (self.lock_blink_counter // strobe_frequency) % 2 == 0:
            # Light red vignette (very subtle)
            vignette_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
            vignette_color = (*theme.RED, 25)  # Lower alpha
            pygame.draw.rect(vignette_surface, vignette_color, (0, 0, screen_width, screen_height))
            self.screen.blit(vignette_surface, (0, 0))

            # Small red X in corners only (not full viewport)
            x_color = theme.RED_BRIGHT
            x_size = 30
            thickness = 2

            # Top-Left X
            pygame.draw.line(self.screen, x_color,
                             (world_left, world_top), (world_left + x_size, world_top + x_size), thickness)
            pygame.draw.line(self.screen, x_color,
                             (world_left + x_size, world_top), (world_left, world_top + x_size), thickness)

            # Top-Right X
            pygame.draw.line(self.screen, x_color,
                             (world_right, world_top), (world_right - x_size, world_top + x_size), thickness)
            pygame.draw.line(self.screen, x_color,
                             (world_right - x_size, world_top), (world_right, world_top + x_size), thickness)

            # Thin red border pulse
            pygame.draw.rect(self.screen, theme.RED_BRIGHT,
                             (world_left, world_top, world_right - world_left, world_bottom - world_top),
                             2)

    def draw_dfs_warning(self, active, timer=0.0):
        """Draw pulsing scan sweep when being swept by DFS.

        Args:
            active: Boolean indicating if warning should display
            timer: Current timer value (0-3 seconds). Caller handles incrementing.
        """
        if not active:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        center_x = (world_left + world_right) // 2
        center_y = (world_top + world_bottom) // 2

        # Pulse intensity based on time (0-1)
        pulse = (timer % 1.0)
        alpha = int(200 * (1.0 - pulse))  # Fade out as pulse completes

        scan_color = (*theme.RED, alpha)

        # Draw expanding concentric circles (scan sweep effect)
        max_radius = 150
        radius = int(max_radius * pulse)

        scan_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        pygame.draw.circle(scan_surface, scan_color, (center_x, center_y), radius, 2)
        pygame.draw.circle(scan_surface, scan_color, (center_x, center_y), max(radius - 20, 0), 1)
        self.screen.blit(scan_surface, (0, 0))

        # Corner warning indicators
        indicator_color = theme.RED
        indicator_size = 8
        pygame.draw.circle(self.screen, indicator_color, (world_left + 15, world_top + 15), indicator_size, 2)
        pygame.draw.circle(self.screen, indicator_color, (world_right - 15, world_top + 15), indicator_size, 2)

        # Status line at a fixed position, left-aligned under the corner indicator
        warning_text = self.font_scan_body.render("STATUS: DFS SWEEP DETECTED", True, theme.RED)
        self.screen.blit(warning_text, (world_left + 32, world_top + 30))

    def draw_missile_contact(self, time_left, duration=1.5):
        """Banner at the top of the viewport confirming a missile reached its contact.

        Args:
            time_left: Seconds remaining (counts down to 0). Caller handles the timer.
            duration: Total display time, used to compute the fade.
        """
        if time_left <= 0:
            return

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        # No fade-in/fade-out (that's a toast notification). The readout is either
        # lit or not: hard flicker as the hit registers, steady, then it stutters
        # out over the last third like the line is being cleared.
        elapsed = duration - time_left
        if elapsed < 0.25 and int(elapsed * 30) % 2:
            return
        if time_left < duration / 3 and int(time_left * 12) % 2:
            return

        text = self.font_scan_header.render("MSL STATUS: CONTACT CONFIRMED", True, theme.AMBER_BRIGHT)
        pad_x, pad_y = 18, 8
        box = pygame.Rect(0, 0, text.get_width() + pad_x * 2, text.get_height() + pad_y * 2)
        box.topleft = (world_left + 16, world_top + 64)
        self._frame(box, theme.AMBER, fill=theme.BG, tick=6)
        self.screen.blit(text, (box.left + pad_x, box.top + pad_y))

    def draw_deep_field_panel(self, contacts, direction_index, system_online=True):
        screen_height = self.screen.get_height()

        # Panel geometry: the same full-height panel whether the scan is on or off,
        # so nothing changes shape when it's switched
        panel_x = self.DFS_PANEL_MARGIN
        panel_width = 560
        panel_y = self.THIN_HEIGHT + self.DFS_PANEL_MARGIN
        panel_height = (
                screen_height - panel_y - self.THIN_HEIGHT - self.DFS_PANEL_MARGIN
        ) // 2
        rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        self._frame(rect, self.COLOR_DFS_BORDER, fill=self.COLOR_DFS_BG, width=2)

        directions = [
            ("N", "000"), ("NE", "045"), ("E", "090"), ("SE", "135"),
            ("S", "180"), ("SW", "225"), ("W", "270"), ("NW", "315"),
        ]
        direction, degrees = directions[direction_index % 8]

        # Panel name on the top border, as on the laser box
        name = self.font_tiny.render(f" DEEP FIELD SCAN // {direction} {degrees}° ", True, self.COLOR_DFS_BORDER)
        tab = name.get_rect(midleft=(panel_x + 14, rect.top))
        pygame.draw.rect(self.screen, self.COLOR_DFS_BG, tab)
        self.screen.blit(name, tab)

        x = panel_x + 15
        right = panel_x + panel_width - 15
        mid = rect.top + rect.height // 2

        total_contacts = len(contacts)
        moving_count = sum(1 for c in contacts if c[2])
        static_count = total_contacts - moving_count
        high_conf = sum(1 for c in contacts if c[3] >= 0.75)
        med_conf = sum(1 for c in contacts if 0.5 <= c[3] < 0.75)
        low_conf = sum(1 for c in contacts if c[3] < 0.5)

        # --- Top half: status and summary ---
        y = rect.top + 30
        if system_online:
            status = self.font_scan_body.render("STATUS: ONLINE", True, self.COLOR_DFS_GREEN)
            self.screen.blit(status, (x, y))
            y += 40
            summary = [
                (f"CONTACTS: {total_contacts}", self.COLOR_DFS_DATA),
                (f"MOVING: {moving_count}    STATIONARY: {static_count}", self.COLOR_DFS_WHITE),
                (f"CONFIDENCE: {high_conf} HIGH | {med_conf} MED | {low_conf} LOW", self.COLOR_DFS_AMBER),
            ]
            for text, color in summary:
                self.screen.blit(self.font_scan_body.render(text, True, color), (x, y))
                y += 28
        else:
            status = self.font_scan_body.render("STATUS: OFFLINE", True, self.COLOR_DFS_GRAY)
            self.screen.blit(status, (x, y))

        pygame.draw.line(self.screen, self.COLOR_DFS_INSET, (x, mid), (right, mid))

        # --- Bottom half: contact list, then the controls ---
        controls = pygame.Rect(panel_x + 15, rect.bottom - 15 - 42, panel_width - 30, 42)
        self._button_row(controls, [
            (2, "< BRG", 'dfs_bearing_ccw', dict(key="DN", enabled=system_online)),
            (2, "BRG >", 'dfs_bearing_cw', dict(key="UP", enabled=system_online)),
            (3, "RUN SCAN", 'dfs_scan', dict(key="O", enabled=system_online)),
            (2, "PWR", 'toggle_dfs', dict(key="K", lit=system_online)),
        ])
        list_bottom = controls.top - 10

        y = mid + 16
        if not system_online:
            heading = self.font_scan_body.render("NO SIGNAL", True, self.COLOR_DFS_GRAY)
            self.screen.blit(heading, (x, y))
        elif moving_count > 0:
            heading = self.font_scan_body.render("MOVING CONTACTS:", True, self.COLOR_DFS_GREEN)
            self.screen.blit(heading, (x, y))
            y += 28

            moving_contacts = sorted([c for c in contacts if c[2]], key=lambda c: c[3], reverse=True)

            # As many as fit above the control row
            room = max(0, (list_bottom - y) // 25)
            shown = min(len(moving_contacts), room)
            if shown < len(moving_contacts):
                shown = max(0, shown - 1)  # leave a line for the "+N MORE"

            for rng, ctype, _, confidence, _ in moving_contacts[:shown]:
                conf_level = "HIGH" if confidence >= 0.75 else "MED" if confidence >= 0.5 else "LOW"
                line = f"  {ctype.upper():10} [{conf_level} {int(confidence * 100)}%]"

                txt = self.font_scan_body.render(line, True, self.COLOR_DFS_YELLOW)
                self.screen.blit(txt, (x, y))
                y += 25

            hidden = len(moving_contacts) - shown
            if hidden > 0 and y + 25 <= list_bottom:
                more = self.font_scan_body.render(f"  +{hidden} MORE", True, self.COLOR_DFS_GRAY)
                self.screen.blit(more, (x, y))
        else:
            no_threat = self.font_scan_body.render("NO MOVING CONTACTS", True, self.COLOR_DFS_GRAY)
            self.screen.blit(no_threat, (x, y))

    def draw_dfs_corridor(self, player_ship, dfs_direction_index, camera_x, camera_y, active=False):
        if not active:
            return

        """Draw deep field scan as an amber baseline perpendicular to the scan heading,
        centered on the player, with chevron arrows on the main viewport (cleared at center)
        and orange directional scan lines extending edge-to-edge on the radar panel."""
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        radar_x, radar_y, radar_size = self._get_radar_bounds()

        directions = [0, 45, 90, 135, 180, 225, 270, 315]
        direction_deg = directions[dfs_direction_index % 8]

        origin_x, origin_y = player_ship.rect.center

        # Direction vectors
        rad = math.radians(direction_deg - 90)
        forward_x = math.cos(rad)
        forward_y = math.sin(rad)

        # Perpendicular vector (rotated 90 degrees)
        perp_x = -forward_y
        perp_y = forward_x

        # Distance long enough to extend past screen/radar edges in both directions
        line_extent = 20000

        # Calculate main baseline endpoints in world space
        start_x = origin_x - perp_x * line_extent
        start_y = origin_y - perp_y * line_extent
        end_x = origin_x + perp_x * line_extent
        end_y = origin_y + perp_y * line_extent

        amber_color = self.COLOR_DFS_AMBER
        # Orange color for the radar scan projection lines
        orange_color = self.COLOR_DFS_ORANGE

        # --- Arrow Geometry Configuration (Main Viewport) ---
        arrow_spacing = 400  # Distance between directional arrows along the line
        arrow_size = 20  # Distance the arrow points forward
        arrow_wing_width = 12  # Half-width of the arrow base
        center_clearance = 200  # Skip arrows within this distance from the player center

        arrow_offsets = range(-10000, 10000 + arrow_spacing, arrow_spacing)
        world_arrows = []
        for offset in arrow_offsets:
            if abs(offset) < center_clearance:
                continue

            bx = origin_x + perp_x * offset
            by = origin_y + perp_y * offset

            tip_x = bx + forward_x * arrow_size
            tip_y = by + forward_y * arrow_size

            left_x = bx - perp_x * arrow_wing_width
            left_y = by - perp_y * arrow_wing_width
            right_x = bx + perp_x * arrow_wing_width
            right_y = by + perp_y * arrow_wing_width

            world_arrows.append((
                (left_x, left_y),
                (tip_x, tip_y),
                (right_x, right_y)
            ))

        # --- 1. World Viewport Drawing ---
        viewport = pygame.Rect(world_left, world_top, world_right - world_left, world_bottom - world_top)
        self.screen.set_clip(viewport)

        # Main perpendicular baseline
        screen_start = (start_x - camera_x, start_y - camera_y)
        screen_end = (end_x - camera_x, end_y - camera_y)
        pygame.draw.line(self.screen, amber_color, screen_start, screen_end, 2)

        # Draw directional chevron arrows along the line
        for wing_l, tip, wing_r in world_arrows:
            pts = [
                (wing_l[0] - camera_x, wing_l[1] - camera_y),
                (tip[0] - camera_x, tip[1] - camera_y),
                (wing_r[0] - camera_x, wing_r[1] - camera_y)
            ]
            pygame.draw.lines(self.screen, amber_color, False, pts, 2)

        self.screen.set_clip(None)

        # --- 2. Radar Panel Drawing ---
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2
        radar_scale = radar_size / self.RADAR_SCALE

        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        self.screen.set_clip(radar_rect)

        # Convert main baseline endpoints to radar coordinates
        radar_start = (
            center_x + (start_x - origin_x) * radar_scale,
            center_y + (start_y - origin_y) * radar_scale
        )
        radar_end = (
            center_x + (end_x - origin_x) * radar_scale,
            center_y + (end_y - origin_y) * radar_scale
        )

        # Radar baseline (Amber)
        pygame.draw.line(self.screen, amber_color, radar_start, radar_end, 1)

        # Orange scan lines extending perpendicularly off the amber baseline out to radar edges
        radar_line_spacing = 1000  # Interval along the baseline for radar orange indicators
        for offset in range(-10000, 10000 + radar_line_spacing, radar_line_spacing):
            # Anchor point on the amber baseline in world space
            bx = origin_x + perp_x * offset
            by = origin_y + perp_y * offset

            # Radar screen coordinate for baseline anchor
            anchor_rx = center_x + (bx - origin_x) * radar_scale
            anchor_ry = center_y + (by - origin_y) * radar_scale

            # Project a ray forward along the scan direction to radar edge
            end_rx = anchor_rx + forward_x * line_extent
            end_ry = anchor_ry + forward_y * line_extent

            pygame.draw.line(self.screen, orange_color, (anchor_rx, anchor_ry), (end_rx, end_ry), 1)

        self.screen.set_clip(None)

    def draw_corpo_miner_fire_warning(self, pirate_firing):
        """Draw a single orange line sweeping left to right across viewport.

        Args:
            pirate_firing: Boolean indicating if pirates have lock and are firing
        """
        if not pirate_firing:
            return

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        viewport_width = world_right - world_left

        # Timing
        if not hasattr(self, 'pirate_sweep_counter'):
            self.pirate_sweep_counter = 0

        self.pirate_sweep_counter += 1

        # Sweep position (0.0 to 1.0, then repeat)
        sweep_progress = (self.pirate_sweep_counter * 0.02) % 1.0
        line_x = world_left + (sweep_progress * viewport_width)

        # Pulsing brightness
        pulse = 0.4 + 0.6 * abs(math.sin(self.pirate_sweep_counter * 0.05))
        brightness = int(255 * pulse)
        color = (brightness, brightness // 4, brightness // 5)

        # Draw vertical line
        pygame.draw.line(self.screen, color,
                         (line_x, world_top),
                         (line_x, world_bottom),
                         2)

        # Draw "PIRATE LOCK" text at top center
        if not hasattr(self, 'font_pirate_lock'):
            self.font_pirate_lock = fonts.legacy_font(24)

        # Text pulses between readable and bright, never as dim as the sweep line
        text_color = theme.RED if pulse < 0.7 else theme.RED_BRIGHT
        warning_text = self.font_pirate_lock.render("HOSTILE GUN SOLUTION DETECTED", True, text_color)
        text_rect = warning_text.get_rect(midtop=((world_left + world_right) // 2, world_top + 18))
        pygame.draw.rect(self.screen, theme.BLACK, text_rect.inflate(16, 6))
        self.screen.blit(warning_text, text_rect)

    def draw_bullet_damage_glitch(self, ship_took_damage):

        if not ship_took_damage:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # Create glitch surface
        glitch = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)

        # Random horizontal line disruptions
        num_glitch_lines = random.randint(3, 8)
        for _ in range(num_glitch_lines):
            glitch_y = random.randint(0, screen_height)
            glitch_height = random.randint(2, 8)
            glitch_width = random.randint(100, 400)
            glitch_x = random.randint(0, screen_width - glitch_width)

            # Bright white/cyan distortion
            glitch_color = (255, 255, random.randint(100, 200), 120)
            pygame.draw.rect(glitch, glitch_color, (glitch_x, glitch_y, glitch_width, glitch_height))

        self.screen.blit(glitch, (0, 0))

    IMPACT_DURATION = 0.7  # seconds the flicker lasts after the last contact

    def draw_impact_failure(self, strength, elapsed):
        """Non-fatal hull hit: the signal flickers as if the link nearly dropped.

        strength runs 1 -> 0 over IMPACT_DURATION. A few rapid dropouts toward dim,
        with a faint tear now and then, then the picture settles back.
        """
        s = max(0.0, min(1.0, strength))
        if s <= 0:
            return
        screen = self.screen
        w, h = screen.get_size()

        # Tearing: several thin bands jump sideways, more of them as strength rises
        if random.random() < 0.9 * s:
            y = random.randrange(h)
            reach = int(8 + 14 * s)
            for _ in range(random.randint(2, 2 + int(4 * s))):
                bh = random.randint(2, 14)
                rect = pygame.Rect(0, y, w, bh).clip(screen.get_rect())
                if rect.height <= 0:
                    break
                strip = screen.subsurface(rect).copy()
                screen.blit(strip, (random.randint(-reach, reach), rect.y))
                y = (y + bh + random.randint(6, 60)) % h

        # Dropouts: the picture blinks dim, a few times, faster than a blink
        if random.random() < 0.6 * s:
            dim = pygame.Surface((w, h), pygame.SRCALPHA)
            dim.fill((0, 0, 0, int(140 * s)))
            screen.blit(dim, (0, 0))

    def draw_low_health_warning(self, low_health):
        """Draw flashing red warning box in bottom left of viewport.

        Args:
            low_health: Boolean indicating if ship is at low health
        """
        if not low_health:
            return

        world_left, _, _, world_bottom = self._get_world_bounds()

        # Box position and size (bottom left)
        box_x = world_left + 10
        box_y = world_bottom - 120
        box_w = 150
        box_h = 100

        # Simple blink (on/off)
        if not hasattr(self, 'health_blink_counter'):
            self.health_blink_counter = 0

        self.health_blink_counter += 1
        blink_frequency = 10  # Frames on/off

        # Only draw if in "on" state of blink
        if (self.health_blink_counter // blink_frequency) % 2 == 0:
            color = theme.RED

            # Draw box
            pygame.draw.rect(self.screen, color, (box_x, box_y, box_w, box_h), 2)

            # Draw simple X
            pygame.draw.line(self.screen, color,
                             (box_x, box_y),
                             (box_x + box_w, box_y + box_h), 2)
            pygame.draw.line(self.screen, color,
                             (box_x + box_w, box_y),
                             (box_x, box_y + box_h), 2)

            # Draw text
            if not hasattr(self, 'font_critical'):
                self.font_critical = fonts.font(15)

            text = self.font_critical.render("HULL CRITICAL", True, color)
            text_x = box_x + (box_w - text.get_width()) // 2
            text_y = box_y + box_h - text.get_height() - 6
            self.screen.blit(text, (text_x, text_y))
