import math
import zlib
import random
from datetime import datetime

import pygame
from config.constants import *
from config import theme
from config import ui_constants
from asset_handlers import fonts
from asset_handlers.buttons import ButtonLayer, draw_button, draw_frame
from asset_handlers.crt import crt
from asset_handlers.grime import build_panel
from utility.text_input import blink_cursor
from simulation.settings import WorldSettings
from utility.geometry import map_to_range_linear


class DrawUI:
    # region constant
    PANEL_WIDTH = 600
    THIN_HEIGHT = 200

    # Radar Configuration
    RADAR_PADDING = ui_constants.RADAR_PADDING
    RADAR_SCALE = ui_constants.RADAR_SCALE  # World units across the radar

    # Corridor Dimensions
    CORRIDOR_WIDTH = CORRIDOR_WIDTH
    CORRIDOR_DEPTH = CORRIDOR_DEPTH

    # DFS Configuration
    DFS_MAX_RANGE = 5000
    DFS_PANEL_MARGIN = 20
    DFS_CONTACT_DISPLAY_LIMIT = 8


    # Colour palette: see config/theme.py for what each colour means
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
    COLOR_LASER_ACTIVE = theme.GREEN  # your beam is a sensor
    COLOR_LASER_PAINTED = theme.AMBER_BRIGHT  # ...that has something on it

    # Threat/Warning Colors
    COLOR_THREAT_RED = theme.RED
    COLOR_THREAT_DIM = theme.RED_DIM
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
        self.world_width = self.world_height = WorldSettings().size  # set per match by set_world
        self.lock_blink_counter = 0
        self.buttons = ButtonLayer()

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

        self.tutorial_splash_elapsed = 0.0

    # Menu stuff

    def draw_text_screen(self, title, lines, footer="", header="", buttons=(), show=True):
        """A framed console, same style as the in-game operator console: header
        strip, title, readout lines, a column of buttons
        [(label, key hint, action) or (label, key hint, action, enabled)],
        and a fault line (`footer`) or the input prompt along the bottom."""
        if not show:
            return
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

    def draw_debrief_screen(self, status, detail, options, show=True):
        """End-of-mission readout: plain left-aligned fields on black, no frame or
        ornament. Each option is an underlined text line that is its own click area.
        options: [(action, label, key hint), ...], top to bottom."""
        if not show:
            return
        from datetime import datetime, timezone

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

        self.draw_options(options)

        self.buttons.end_frame()

    def draw_certificate(self, callsign, show=True):
        """A framed certificate of completion, centred, with two decorative buttons
        (DOWNLOAD, PRINT) under it. The buttons are drawn but never registered, so they
        do nothing when clicked."""
        if not show:
            return
        w, h = self.screen.get_size()
        self.screen.fill(theme.BLACK)

        cert_w = min(860, w - 80)
        cert_h = min(560, h - 200)
        btn_h, btn_gap_y = 50, 24
        group_top = (h - (cert_h + btn_gap_y + btn_h)) // 2
        cert = pygame.Rect(0, 0, cert_w, cert_h)
        cert.midtop = (w // 2, group_top)

        self._frame(cert, theme.AMBER, fill=theme.BLACK, tick=10, width=2)
        inner = cert.inflate(-24, -24)

        def centred(surf, y):
            self.screen.blit(surf, surf.get_rect(midtop=(cert.centerx, y)))
            return y + surf.get_height()

        y = centred(self.menu_small_font.render("ERGOT SYSTEMS // FLIGHT TRAINING", True, theme.AMBER_DIM), inner.top + 28)
        y = centred(self.menu_title_font.render("CERTIFICATE OF COMPLETION", True, theme.AMBER_BRIGHT), y + 20)
        rule_y = y + 16
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (cert.left + 80, rule_y), (cert.right - 80, rule_y))

        y = centred(self.menu_small_font.render("THIS CERTIFIES THAT", True, theme.AMBER_DIM), rule_y + 36)
        y = centred(self.menu_title_font.render(callsign.upper(), True, theme.GREEN_BRIGHT), y + 8)
        y = centred(self.menu_font.render("has completed flight certification", True, theme.GREEN), y + 20)
        y = centred(self.menu_font.render("and is cleared to remote pilot class 42 drones", True, theme.GREEN), y + 8)

        date_text = datetime.now().strftime("%Y-%m-%d")
        sign_y = inner.bottom - 50
        left_x = inner.left + 70
        right_x = inner.right - 70
        pygame.draw.line(self.screen, theme.AMBER_DIM, (left_x, sign_y), (left_x + 240, sign_y))
        pygame.draw.line(self.screen, theme.AMBER_DIM, (right_x - 240, sign_y), (right_x, sign_y))
        date_surf = self.menu_small_font.render("DATE: " + date_text, True, theme.AMBER)
        self.screen.blit(date_surf, date_surf.get_rect(midbottom=(left_x + 120, sign_y - 6)))
        officer_surf = self.menu_small_font.render("TRAINING OFFICER", True, theme.AMBER)
        self.screen.blit(officer_surf, officer_surf.get_rect(midbottom=(right_x - 120, sign_y - 6)))

        seal_center = (cert.centerx, sign_y - 10)
        pygame.draw.circle(self.screen, theme.AMBER_DIM, seal_center, 34, 2)
        pygame.draw.circle(self.screen, theme.AMBER_FAINT, seal_center, 26, 1)

        btn_w, btn_h, btn_gap = 200, btn_h, 16
        btn_y = cert.bottom + btn_gap_y
        total_w = btn_w * 2 + btn_gap
        left = w // 2 - total_w // 2
        for i, label in enumerate(("DOWNLOAD", "PRINT")):
            rect = pygame.Rect(left + i * (btn_w + btn_gap), btn_y, btn_w, btn_h)
            draw_button(self.screen, rect, label, align="center", font=self.menu_font, key_font=self.menu_key_font)

    def draw_options(self, options, show=True):
        """Underlined text options down the bottom-left: [(action, label, key hint or None), ...]."""
        if not show:
            return
        x0 = 40
        w, h = self.screen.get_size()
        body = self.menu_font
        head = self.menu_small_font
        step = body.get_height() + 14
        first_y = h - 48 - (len(options) - 1) * step
        for i, (action, label, key_hint) in enumerate(options):
            y = first_y + i * step
            text = body.render(label, True, theme.AMBER)
            key = head.render(f"  [{key_hint}]", True, theme.AMBER_DIM) if key_hint else pygame.Surface((0, 0))
            self.screen.blit(text, (x0, y))
            self.screen.blit(key, key.get_rect(bottomleft=(x0 + text.get_width(), y + text.get_height())))
            underline_y = y + text.get_height() + 2
            pygame.draw.line(self.screen, theme.AMBER_DIM, (x0, underline_y), (x0 + text.get_width() + key.get_width(), underline_y))
            click = pygame.Rect(x0 - 8, y - 6, text.get_width() + key.get_width() + 16, text.get_height() + 12)
            self.buttons.register(click, action)

    def draw_spectate_hud(self, callsign, watched, number, total, options, show=True):
        """The HUD once our own ship is gone: the same panels and readouts, in the
        error state. Values read as dashes and the boxes are red. The only live
        controls are the ones that still work: watching another pilot and leaving.

        callsign: our own (lost) pilot name. watched: the pilot the camera is on.
        number, total: which living pilot we're watching, out of how many.
        options: [(action, label, key hint), ...] as for draw_options.
        """
        if not show:
            return
        ERR = theme.RED
        ERR_DIM = theme.RED_DIM
        ERR_BRIGHT = theme.RED_BRIGHT
        blink_on = (pygame.time.get_ticks() // 400) % 2 == 0
        pad = 22
        small = fonts.font(17)
        self.draw_ui_layout()

        # Pilot ID: our callsign, with the link down
        rect = self._callsign_rect()
        self._frame(rect, ERR)
        self._box_title(rect, "PILOT ID // LOST", ERR)
        name = callsign or "UNREGISTERED"
        big = fonts.font(34)
        name_surf = big.render(name, True, ERR_BRIGHT)
        if name_surf.get_width() > rect.width - 2 * pad:
            name_surf = fonts.font(26).render(name, True, ERR_BRIGHT)
        name_y = rect.top + 8 + self.BOX_HEAD + 14
        self.screen.blit(name_surf, (rect.left + pad, name_y))
        rule_y = name_y + big.get_height() + 6
        pygame.draw.line(self.screen, ERR_DIM, (rect.left + pad, rule_y), (rect.right - pad, rule_y))
        value_x = rect.left + pad + small.size("IFF ")[0] + 14
        y = rule_y + 10
        for label, value in (("IFF", "--- ---"), ("LINK", "SIGNAL LOST")):
            self.screen.blit(small.render(label, True, ERR_DIM), (rect.left + pad, y))
            self.screen.blit(small.render(value, True, ERR), (value_x, y))
            y += small.get_height() + 4

        # Signal relay: the pilot we are watching, with PREV / NEXT
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        top = self._get_panel_rects()[0]
        relay = pygame.Rect(rect.right + 24, rect.top, max(160, radar_x - 24 - (rect.right + 24)), rect.height)
        self._frame(relay, ERR)
        self._box_title(relay, "SIGNAL RELAY", ERR)
        self.screen.blit(small.render(f"WATCHING {number:02d} OF {total:02d}", True, ERR_DIM),
                         (relay.left + pad, relay.top + 34))
        self.screen.blit(fonts.font(26).render(watched, True, theme.GREEN),
                         (relay.left + pad, relay.top + 34 + small.get_height() + 4))
        bh = 34
        bw = (relay.width - 2 * pad - 10) // 2
        by = relay.bottom - 16 - bh
        self._button((relay.left + pad, by, bw, bh), "< PREV", 'spectate_prev', enabled=total > 1)
        self._button((relay.left + pad + bw + 10, by, bw, bh), "NEXT >", 'spectate_next', enabled=total > 1)

        # Power: where the fuel and draw readouts would be
        power = pygame.Rect(radar_x, top.top + 22, radar_size, top.height - 44)
        self._frame(power, ERR)
        self._box_title(power, "POWER // NO FEED", ERR)
        readout = fonts.font(26)
        y = power.top + 34
        self.screen.blit(readout.render("FUEL", True, ERR_DIM), (power.left + pad, y))
        self.screen.blit(readout.render(f"|{'-' * 6}|", True, ERR), (power.left + pad + 110, y))
        y += readout.get_height() + 6
        self.screen.blit(readout.render("DRAW", True, ERR_DIM), (power.left + pad, y))
        dash = readout.render("----", True, ERR)
        self.screen.blit(dash, dash.get_rect(topright=(power.right - pad, y)))
        alert = fonts.font(20).render("CARRIER LOST", True, ERR)
        if blink_on:
            box = pygame.Rect(0, 0, alert.get_width() + 24, alert.get_height() + 12)
            box.midbottom = (power.centerx, power.bottom - 14)
            self._frame(box, ERR, tick=8, width=2)
            self.screen.blit(alert, alert.get_rect(center=box.center))

        # Radar: no returns
        radar = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        self._frame(radar, ERR, tick=12)
        self._box_title(radar, "RADAR // NO RETURNS", ERR)
        if blink_on:
            msg = fonts.font(34).render("NO SIGNAL", True, ERR)
            self.screen.blit(msg, msg.get_rect(center=radar.center))

        # Telemetry: the same three columns as ship info, all dashes
        font = fonts.font(19)
        line_h = font.get_height() + 3
        columns = [
            [("NAV-COM", ERR_DIM), ("POS  X ------  Y ------", ERR), ("GRID --", ERR),
             ("VEL  X ----  Y ----", ERR), (f"SPD  --- / {SHIP_MAX_SPEED:03d} U", ERR), ("HDG  --- DEG", ERR)],
            [("SUBSYSTEMS", ERR_DIM), ("INERT DAMP  [--]", ERR), ("BRAKE       [--]", ERR), ("LINK DOWN", ERR)],
            [("TACTICAL", ERR_DIM), ("THREAT  NO DATA", ERR), ("MSL  --/--  NO FEED", ERR), ("HULL  000/100", ERR)],
        ]
        rendered = [[font.render(t, True, c) for t, c in col] for col in columns]
        col_w = [max(s.get_width() for s in col) for col in rendered]
        gap = 44
        box_w = sum(col_w) + gap * (len(columns) - 1) + 2 * pad
        box_h = self.THIN_HEIGHT - 24
        _, _, _, world_bottom = self._get_world_bounds()
        tele = pygame.Rect(24, world_bottom + 12, box_w, box_h)
        self._frame(tele, ERR)
        rows = max(len(c) for c in columns)
        y0 = tele.top + (box_h - rows * line_h) // 2 + 4
        x = tele.left + pad
        for col, cw in zip(rendered, col_w):
            for i, surf in enumerate(col):
                self.screen.blit(surf, (x, y0 + i * line_h))
            pygame.draw.line(self.screen, ERR_DIM, (x, y0 + line_h - 2), (x + cw, y0 + line_h - 2))
            x += cw + gap

        # Controls: the only live buttons left (watch, return)
        bank_left = tele.right + 48
        bank_w = self.screen.get_width() - 24 - bank_left
        if bank_w >= 150 and options:
            bank = pygame.Rect(bank_left, tele.top, bank_w, tele.height)
            self._frame(bank, ERR, tick=8)
            self._box_title(bank, "CONTROLS // OFFLINE", ERR, steady=True)
            inner = pygame.Rect(bank.left + 14, bank.top + 24, bank.width - 28, bank.height - 38)
            n, bgap = len(options), 8
            bw = min(360, (inner.width - bgap * (n - 1)) // n)
            bh = min(52, inner.height)
            by = inner.centery - bh // 2
            for i, (action, label, key_hint) in enumerate(options):
                self._button((inner.left + i * (bw + bgap), by, bw, bh), label, action, key=key_hint)

    def draw_splash_screen(self, enabled: bool, timer: float, show=True):
        """Boot screen in the operator-console style: a small system identification
        strip, labelled sections with left-aligned fields, a scrolling boot log with
        status words, and a load block that states progress as numbers and text."""
        if not show:
            return
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

        ident_font = fonts.font(20)
        field_font = fonts.font(30)
        boot_font = fonts.font(24)
        status_font = fonts.font(22)

        # Same full-window panel and type scale as the main menu
        margin, pad = 16, 28
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, FRAME, fill=theme.BG, tick=14, width=2)

        x0, x1 = panel.left + pad, panel.right - pad
        utc = datetime.now(timezone.utc).strftime("%H:%M:%S")

        # ------------------------------------------------------------------
        # System identification strip (small: operational data comes first)
        # ------------------------------------------------------------------
        y = self._ident_strip(panel, x0, x1, ident_font, HEAD, RULE)

        # ------------------------------------------------------------------
        # System identification: fixed two-column field grid
        # ------------------------------------------------------------------
        line_h = field_font.get_height() + 12
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
                self.screen.blit(field_font.render(value, True, LOG), (fx + 220, fy))
        y = id_box.bottom + 14

        # ------------------------------------------------------------------
        # Load block, pinned to the bottom of the frame
        # ------------------------------------------------------------------
        load_h = 130 + self.BOX_HEAD
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

    TUTORIAL_SPLASH_SECONDS = 4.0
    TUTORIAL_SPLASH_ORBIT_SCALE = 1.35  # size of the ship's lap relative to the ring
    TUTORIAL_SPLASH_BAR_LENGTH = 27  # '#' characters in a full loading bar

    # Call every frame with the frame time; returns True once the splash has run its course
    def draw_tutorial_splash(self, dt):
        self.tutorial_splash_elapsed += dt
        progress = min(1.0, self.tutorial_splash_elapsed / self.TUTORIAL_SPLASH_SECONDS)

        w, h = self.screen.get_size()
        self.screen.fill(theme.BLACK)
        panel = pygame.Rect(16, 16, w - 32, h - 32)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)

        title = self.menu_title_font.render("ERGOT SYSTEMS TRAINING MODULE", True, theme.AMBER_BRIGHT)
        title_rect = title.get_rect(midtop=(panel.centerx, panel.top + 28))
        self.screen.blit(title, title_rect)

        view_top = title_rect.bottom + 20
        view = pygame.Rect(panel.left + 28, view_top, panel.width - 56, panel.bottom - 70 - view_top)
        self._frame(view, theme.AMBER_DIM, fill=theme.BLACK, tick=8)

        cx, cy = view.center
        ring_rx = int(min(view.width, view.height) * 0.36)
        ring_ry = int(ring_rx * 0.45)

        self._draw_splash_ring_half((cx, cy), ring_rx, ring_ry, 180, theme.AMBER_DIM)
        self._draw_splash_ring_half((cx, cy), ring_rx, ring_ry, 0, theme.AMBER)

        # The ship flies one lap outside the ring, starting at the near side, nose along its path
        orbit_rx = ring_rx * self.TUTORIAL_SPLASH_ORBIT_SCALE
        orbit_ry = ring_ry * self.TUTORIAL_SPLASH_ORBIT_SCALE
        angle = math.radians(90 + 360 * progress)
        position = (cx + orbit_rx * math.cos(angle), cy + orbit_ry * math.sin(angle))
        travel_x = -orbit_rx * math.sin(angle)
        travel_y = orbit_ry * math.cos(angle)
        travel_length = math.hypot(travel_x, travel_y)
        self._draw_splash_ship(position, (travel_x / travel_length, travel_y / travel_length))

        filled = int(self.TUTORIAL_SPLASH_BAR_LENGTH * progress)
        bar_text = "|" + ("#" * filled).ljust(self.TUTORIAL_SPLASH_BAR_LENGTH) + "|"
        bar = self.menu_font.render(bar_text, True, theme.AMBER)
        bar_rect = bar.get_rect(midtop=(panel.centerx, view.bottom + 12))
        self.screen.blit(bar, bar_rect)

        return self.tutorial_splash_elapsed >= self.TUTORIAL_SPLASH_SECONDS

    # One half of the ring as an elliptical arc. 0 is the near half, 180 the far half
    def _draw_splash_ring_half(self, center, rx, ry, start_degrees, color):
        points = []
        for degrees in range(start_degrees, start_degrees + 181, 5):
            radians = math.radians(degrees)
            points.append((center[0] + rx * math.cos(radians), center[1] + ry * math.sin(radians)))
        pygame.draw.lines(self.screen, color, False, points, 3)

    # Arrowhead with a notched back: nose forward, two swept-back corners, a notch between them
    def _draw_splash_ship(self, position, forward):
        side = (-forward[1], forward[0])

        def ship_point(local_x, local_y):
            return (position[0] + local_x * forward[0] + local_y * side[0],
                    position[1] + local_x * forward[1] + local_y * side[1])

        nose_len, half_width = 22, 13
        points = [ship_point(nose_len, 0),
                  ship_point(-nose_len * 0.7, half_width),
                  ship_point(-nose_len * 0.35, 0),
                  ship_point(-nose_len * 0.7, -half_width)]
        pygame.draw.polygon(self.screen, theme.AMBER_BRIGHT, points)

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

    def draw_main_menu(self, title, callsign, buttons, footer="", show=True):
        """The main menu, laid out like the boot screen: identification strip, a
        title, a pilot-record field grid, a framed command grid, and a status
        block along the bottom. `buttons` is [(label, key hint, action)]; each is
        registered in the same call that draws it."""
        if not show:
            return
        from datetime import datetime, timezone

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

        field_font = fonts.font(30)
        status_font = fonts.font(22)
        btn_font = fonts.font(30)
        key_font = fonts.font(20)
        title_font = fonts.font(64)
        small_font = fonts.font(20)
        pad, gap = 28, 22

        # Full-window panel, same frame and type scale as the lobby and settings screens
        margin = 16
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)
        x0, x1 = panel.left + pad, panel.right - pad

        y = self._ident_strip(panel, x0, x1, small_font, HEAD, RULE)

        # Title
        title_surf = title_font.render(title, True, TITLE)
        self.screen.blit(title_surf, (x0, y))
        y += title_surf.get_height() + 26

        # Pilot record: two-column field grid, same as the boot identification block
        line_h = field_font.get_height() + 12
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
                self.screen.blit(field_font.render(value, True, LOG), (fx + 220, fy))
        y = record.bottom + gap

        # Status block pinned to the bottom of the frame
        status_h = 120
        status_box = pygame.Rect(x0, panel.bottom - pad - status_h, x1 - x0, status_h)

        # Command grid fills the space between the record and the status block
        command = pygame.Rect(x0, y, x1 - x0, status_box.top - gap - y)
        self._section(command, "COMMAND")
        btn_h, btn_gap = 66, 14
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

    def _titled_box(self, rect, title, color=theme.AMBER_DIM, text=theme.AMBER):
        """A framed box whose title sits in a gap cut into its top border. Returns the
        y where the box's contents can start."""
        self._frame(rect, color, fill=None, tick=8, width=1)
        surf = fonts.font(20).render(title, True, text)
        tab = pygame.Rect(rect.left + 20, rect.top - surf.get_height() // 2, surf.get_width() + 16, surf.get_height())
        pygame.draw.rect(self.screen, theme.BG, tab)
        self.screen.blit(surf, (tab.left + 8, tab.top))
        return rect.top + surf.get_height() // 2 + 16

    def draw_lobby_screen(self, callsign, your_id, roster, settings_lines, status_lines, buttons, show=True):
        """The flight lobby, laid out over the whole screen in framed boxes: the pilot
        record and the pilots on the net on top, the world parameters and the command
        buttons below, status along the bottom. `roster` is [(player_id, callsign)] in
        order; `buttons` is [(label, key hint, action, enabled)]. Each button is
        registered in the same call that draws it."""
        if not show:
            return
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        flicker = 0.96 + math.sin(pygame.time.get_ticks() / 1000.0 * 35.0) * 0.02

        def lit(col):
            return tuple(int(v * flicker) for v in col)

        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        TITLE = lit(theme.AMBER_BRIGHT)
        LOG = lit(theme.GREEN)
        LOG_HOT = lit(theme.GREEN_BRIGHT)

        title_font = fonts.font(64)
        field_font = fonts.font(30)
        small_font = fonts.font(22)
        btn_font = fonts.font(30)
        key_font = fonts.font(20)
        pad, gap = 28, 22

        margin = 16
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)
        x0, x1 = panel.left + pad, panel.right - pad
        y = self._ident_strip(panel, x0, x1, fonts.font(20), HEAD, RULE)
        title_surf = title_font.render("FLIGHT LOBBY", True, TITLE)
        self.screen.blit(title_surf, (x0, y))
        y += title_surf.get_height() + 26

        # Status block pinned to the bottom of the frame
        status_h = 150
        status_box = pygame.Rect(x0, panel.bottom - pad - status_h, x1 - x0, status_h)

        # Two rows of boxes fill the space above it; the left column is the narrower one
        avail = status_box.top - gap - y
        row1_h = int((avail - gap) * 0.56)
        row2_h = avail - gap - row1_h
        left_w = int((x1 - x0 - gap) * 0.42)
        right_x = x0 + left_w + gap
        right_w = x1 - right_x
        y2 = y + row1_h + gap
        record = pygame.Rect(x0, y, left_w, row1_h)
        roster_box = pygame.Rect(right_x, y, right_w, row1_h)
        world = pygame.Rect(x0, y2, left_w, row2_h)
        command = pygame.Rect(right_x, y2, right_w, row2_h)

        # Pilot record: callsign in a field, then slot and net count
        top = self._titled_box(record, "PILOT RECORD")
        row_h = field_font.get_height() + 18
        value_x = record.left + pad + 200
        field_rect = pygame.Rect(value_x - 14, top - 4, record.right - pad - value_x + 14, field_font.get_height() + 12)
        self._frame(field_rect, theme.AMBER_DIM, fill=theme.BG, tick=6, width=1)
        self.screen.blit(field_font.render("CALLSIGN", True, HEAD), (record.left + pad, top))
        self.screen.blit(field_font.render(callsign + blink_cursor(), True, LOG_HOT), (value_x, top))
        for i, (label, value) in enumerate((("SLOT", f"{your_id:02d}"), ("PILOTS", f"{len(roster)} ON NET"))):
            yy = top + (i + 1) * row_h
            self.screen.blit(field_font.render(label, True, HEAD), (record.left + pad, yy))
            self.screen.blit(field_font.render(value, True, LOG), (value_x, yy))
        hint = small_font.render("ENTER TO CONFIRM", True, HEAD)
        self.screen.blit(hint, (record.left + pad, top + 3 * row_h + 6))

        # Pilots on the net: one box per pilot, yours highlighted, overflow as a count
        top = self._titled_box(roster_box, f"PILOTS ON NET  //  {len(roster)}")
        step = small_font.get_height() + 22
        capacity = max(0, (roster_box.bottom - pad - top) // step)
        shown = roster if len(roster) <= capacity else roster[:max(0, capacity - 1)]
        for i, (player_id, name) in enumerate(shown):
            r = pygame.Rect(roster_box.left + pad, top + i * step, roster_box.width - 2 * pad, step - 8)
            mine = player_id == your_id
            self._frame(r, theme.GREEN if mine else theme.AMBER_FAINT, fill=None, tick=6, width=1)
            pid = small_font.render(f"{player_id:02d}", True, HEAD)
            self.screen.blit(pid, pid.get_rect(midleft=(r.left + 18, r.centery)))
            name_surf = small_font.render(name, True, LOG_HOT if mine else LOG)
            self.screen.blit(name_surf, name_surf.get_rect(midleft=(r.left + 84, r.centery)))
            if mine:
                tag = small_font.render("< YOU", True, LOG_HOT)
                self.screen.blit(tag, tag.get_rect(midright=(r.right - 18, r.centery)))
        if len(roster) > len(shown):
            more = small_font.render(f"+{len(roster) - len(shown)} MORE", True, HEAD)
            self.screen.blit(more, (roster_box.left + pad, top + len(shown) * step + 4))

        # World parameters: one boxed field per setting
        top = self._titled_box(world, "WORLD PARAMETERS")
        step = field_font.get_height() + 22
        for i, line in enumerate(settings_lines):
            r = pygame.Rect(world.left + pad, top + i * step, world.width - 2 * pad, step - 10)
            if r.bottom > world.bottom - pad:
                break
            self._frame(r, theme.AMBER_FAINT, fill=None, tick=6, width=1)
            surf = field_font.render(line, True, LOG)
            self.screen.blit(surf, surf.get_rect(midleft=(r.left + 18, r.centery)))

        # Command: the buttons, stacked and full width
        top = self._titled_box(command, "COMMAND")
        bh, bgap = 66, 14
        total = len(buttons) * bh + (len(buttons) - 1) * bgap
        first = top + max(0, (command.bottom - pad - top - total) // 2)
        for i, (label, key, action, *rest) in enumerate(buttons):
            enabled = rest[0] if rest else True
            rect = pygame.Rect(command.left + pad, first + i * (bh + bgap), command.width - 2 * pad, bh)
            self._button(rect, label, action, key=key, enabled=enabled, font=btn_font, key_font=key_font)

        # Status
        top = self._titled_box(status_box, "STATUS", HEAD, theme.AMBER)
        for i, line in enumerate(status_lines[:2]):
            self.screen.blit(small_font.render(line, True, LOG_HOT), (status_box.left + pad, top + 4 + i * (small_font.get_height() + 10)))
        hint = small_font.render("SELECT BY KEY OR CLICK", True, HEAD)
        self.screen.blit(hint, hint.get_rect(topright=(status_box.right - pad, top + 4)))

        self.buttons.end_frame()

    def draw_settings_screen(self, settings_lines, parameters, back, notice_lines, show=True):
        """The world parameters screen, in the same framed-box layout as the lobby.
        settings_lines: the current world, one line per setting. parameters: [(label, key
        hint, action)] that each change one setting. back: (label, key hint, action).
        notice_lines: the status block along the bottom. Buttons register as they are drawn."""
        if not show:
            return
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        flicker = 0.96 + math.sin(pygame.time.get_ticks() / 1000.0 * 35.0) * 0.02

        def lit(col):
            return tuple(int(v * flicker) for v in col)

        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        TITLE = lit(theme.AMBER_BRIGHT)
        LOG = lit(theme.GREEN)
        LOG_HOT = lit(theme.GREEN_BRIGHT)

        title_font = fonts.font(64)
        field_font = fonts.font(30)
        small_font = fonts.font(22)
        btn_font = fonts.font(30)
        key_font = fonts.font(20)
        pad, gap = 28, 22

        margin = 16
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)
        x0, x1 = panel.left + pad, panel.right - pad
        y = self._ident_strip(panel, x0, x1, fonts.font(20), HEAD, RULE)
        title_surf = title_font.render("WORLD SETTINGS", True, TITLE)
        self.screen.blit(title_surf, (x0, y))
        y += title_surf.get_height() + 26

        # Notice block pinned to the bottom of the frame
        status_h = 150
        status_box = pygame.Rect(x0, panel.bottom - pad - status_h, x1 - x0, status_h)

        # Left: the parameters to change. Right: the current world, then BACK.
        avail = status_box.top - gap - y
        left_w = int((x1 - x0 - gap) * 0.5)
        right_x = x0 + left_w + gap
        right_w = x1 - right_x
        command_h = 150
        world_h = avail - gap - command_h
        params = pygame.Rect(x0, y, left_w, avail)
        world = pygame.Rect(right_x, y, right_w, world_h)
        command = pygame.Rect(right_x, y + world_h + gap, right_w, command_h)

        # Parameters: one full-width button per setting
        top = self._titled_box(params, "PARAMETERS")
        bh, bgap = 74, 16
        total = len(parameters) * bh + (len(parameters) - 1) * bgap
        first = top + max(0, (params.bottom - pad - top - total) // 2)
        for i, (label, key, action) in enumerate(parameters):
            rect = pygame.Rect(params.left + pad, first + i * (bh + bgap), params.width - 2 * pad, bh)
            self._button(rect, label, action, key=key, font=btn_font, key_font=key_font)

        # Current world: one boxed field per setting
        top = self._titled_box(world, "CURRENT WORLD")
        step = field_font.get_height() + 22
        for i, line in enumerate(settings_lines):
            r = pygame.Rect(world.left + pad, top + i * step, world.width - 2 * pad, step - 10)
            if r.bottom > world.bottom - pad:
                break
            self._frame(r, theme.AMBER_FAINT, fill=None, tick=6, width=1)
            surf = field_font.render(line, True, LOG)
            self.screen.blit(surf, surf.get_rect(midleft=(r.left + 18, r.centery)))

        # Command: BACK
        top = self._titled_box(command, "COMMAND")
        label, key, action = back
        rect = pygame.Rect(command.left + pad, top + max(0, (command.bottom - pad - top - 66) // 2),
                           command.width - 2 * pad, 66)
        self._button(rect, label, action, key=key, font=btn_font, key_font=key_font)

        # Notice
        top = self._titled_box(status_box, "NOTICE", HEAD, theme.AMBER)
        for i, line in enumerate(notice_lines[:2]):
            self.screen.blit(small_font.render(line, True, LOG_HOT), (status_box.left + pad, top + 4 + i * (small_font.get_height() + 10)))

        self.buttons.end_frame()

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
        if not specs:
            return

        pad, gap = 14, 8
        head = 24
        rows = (len(specs) + cols - 1) // cols
        inner = pygame.Rect(rect.left + pad, rect.top + head, rect.width - 2 * pad, rect.height - head - pad)
        bw = (inner.width - gap * (cols - 1)) // cols
        bh = min(92, (inner.height - gap * (rows - 1)) // rows)
        top = inner.top + (inner.height - (bh * rows + gap * (rows - 1))) // 2
        big, small, key_font = fonts.font(21), fonts.font(14), fonts.font(14)
        for i, (label, action, kwargs) in enumerate(specs):
            r, c = divmod(i, cols)
            style = dict(font=big, sub_font=small, key_font=key_font, **kwargs)
            self._button((inner.left + c * (bw + gap), top + r * (bh + gap), bw, bh), label, action, **style)

    def draw_control_banks(self, ship, cockpit, blink_busy=False,
                           vectors_on=True, sensor_buttons=(), hidden_buttons=(), show=True):
        """Switch banks in the left column, two buttons per row: helm and weapons on top,
        sensors and displays beneath. The cloaking, deep field scan, laser and material
        assessor keep their buttons on their own panels.
        """
        if not show:
            return
        has_target = getattr(cockpit.target, 'net_id', None) is not None
        can_fire = ship.can_fire_missile() and has_target
        helm = [
            (f"FIRE MSL {ship.total_missiles:02d}", 'fire_missile',
             dict(key="P", lit=cockpit.has_missile_solution, enabled=can_fire, lit_color=theme.AMBER_BRIGHT,
                  states=("LOCK", "----"), sub="LAUNCH AT BEAM TARGET")),
            ("DECOY", 'decoy', dict(key="R-ALT", sub="DEPLOY DUMMY DRONE")),
            ("BLINK", 'blink', dict(key="T", lit=blink_busy, enabled=not blink_busy, lit_color=theme.AMBER_BRIGHT,
                                    states=("BUSY", "RDY"), sub="RANDOM SHORT-RANGE JUMP")),
            ("INERT DAMP", 'toggle_dampening', dict(key="G", lit=ship.dampening, sub="AUTO-SLOW WHEN COASTING")),
            ("SILENT", 'silent', dict(key="Z", sub="POWER DOWN ALL EMITTERS")),
        ]
        displays = [
            *sensor_buttons,
            ("VECTORS", 'toggle_vectors', dict(key="H", lit=vectors_on, sub="HEADING / VELOCITY ARROWS")),
        ]
        helm = [b for b in helm if b[1] not in hidden_buttons]
        displays = [b for b in displays if b[1] not in hidden_buttons]

        left = self._left_column_rect()
        gap = 12
        helm_h = (left.height - gap) // 2
        self._bank(pygame.Rect(left.left, left.top, left.width, helm_h), "HELM // WEAPONS", helm, 2)
        self._bank(pygame.Rect(left.left, left.top + helm_h + gap, left.width, left.height - helm_h - gap),
                   "SENSORS // DISPLAYS", displays, 2)

    def _left_column_rect(self):
        """The control column on the left: between the top and bottom consoles, inset from the edge."""
        h = self.screen.get_height()
        m = self.DFS_PANEL_MARGIN
        return pygame.Rect(m, self.THIN_HEIGHT + m, self.PANEL_WIDTH - 2 * m, h - 2 * self.THIN_HEIGHT - 2 * m)

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

    def draw_ship_info(self, ship, cockpit, instrument_lines=(), dfs_warning='idle', show=True):
        """Ship telemetry: three columns of readouts in the bottom panel, under the viewport.

        Column widths come from the text they hold, so nothing overlaps whatever
        the numbers are; the box grows to fit and stays centred under the viewport.
        dfs_warning: 'active' while a DFS sweep is on us, 'idle', or 'off' (alert muted).
        """
        if not show:
            return
        font = fonts.font(19)
        line_h = font.get_height() + 3

        LIVE = theme.GREEN  # live readouts / system on
        CAUTION = theme.AMBER_BRIGHT
        THREAT = theme.RED
        LABEL = theme.AMBER_DIM  # headings and switched-off systems

        def on(flag):
            return LIVE if flag else LABEL

        # (Navigation lives in its own panel under the deep field scan: see draw_navcom)

        # --- Column 1: subsystems (value in brackets drives the colour) ---
        damp = getattr(ship, "dampening", True)
        braking = getattr(ship, "braking", False)
        subsystems = [
            ("SUBSYSTEMS", LABEL),
            (f"INERT DAMP  [{'ON' if damp else 'OFF'}]", on(damp)),
            (f"BRAKE       [{'ON' if braking else 'OFF'}]", on(braking)),
            *[(text, on(is_on)) for text, is_on in instrument_lines],
        ]

        # --- Column 2: tactical ---
        if ship.missile_cooling_down:
            msl = (f"MSL  {ship.total_missiles:02d}/{TOTAL_MISSILES:02d}  RCHG {ship.missile_cooldown_timer:.1f}S", CAUTION)
        else:
            msl = (f"MSL  {ship.total_missiles:02d}/{TOTAL_MISSILES:02d}  READY", LIVE)
        health = int(getattr(ship, "health", 100))
        hull_col = THREAT if health < 20 else (CAUTION if health < 40 else LIVE)
        if ship.painted or cockpit.enemy_has_missile_solution:
            threat = ("THREAT  LOCK ON YOU" if cockpit.enemy_has_missile_solution else "THREAT  RADAR PAINTED", THREAT)
        elif cockpit.has_missile_solution:
            threat = ("TGT   ON BEAM", CAUTION)
        else:
            threat = ("THREAT  NONE", LABEL)
        # Fixed row, so it never shifts the rows above; gray unless a sweep is on us
        dfs_row = {
            'active': ("THREAT  DFS SWEEP", THREAT),
            'off': ("DFS SWEEP  OFF", LABEL),
        }.get(dfs_warning, ("DFS SWEEP  CLEAR", LABEL))
        tactical = [("TACTICAL", LABEL), threat, msl, (f"HULL  {health:03d}/100", hull_col), dfs_row]

        columns = [subsystems, tactical]
        rendered = [[font.render(t, True, c) for t, c in col] for col in columns]
        col_w = [max(s.get_width() for s in col) for col in rendered]

        pad, gap = 22, 44
        box_w = sum(col_w) + gap * (len(columns) - 1) + pad * 2
        box_h = self.THIN_HEIGHT - 24
        world_left, world_right, _, world_bottom = self._get_world_bounds()
        box = pygame.Rect(0, 0, box_w, box_h)
        box.topleft = (24, world_bottom + 12)  # left end of the bottom strip; the control bank takes the rest
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

    NAVCOM_ROWS = 5

    def _readout_rects(self):
        """The three readout boxes across the bottom console, right of the telemetry:
        (deep field scan, nav-com, cloaking), equal width, sharing the strip's height."""
        w, h = self.screen.get_size()
        top = h - self.THIN_HEIGHT + 12  # same top and height as the telemetry box
        height = self.THIN_HEIGHT - 24
        left = self.PANEL_WIDTH + self.DFS_PANEL_MARGIN
        gap = 12
        slot_w = (w - self.DFS_PANEL_MARGIN - left - 2 * gap) // 3
        return [pygame.Rect(left + i * (slot_w + gap), top, slot_w, height) for i in range(3)]

    def _navcom_rect(self):
        """NAV-COM: the middle readout in the bottom console."""
        return self._readout_rects()[1]

    def _cloak_rect(self):
        """The cloaking box: the right-hand readout in the bottom console."""
        return self._readout_rects()[2]

    def draw_navcom(self, ship, show=True):
        """Navigation readout: in the bottom console, between the deep field scan and cloaking."""
        if not show:
            return
        rect = self._navcom_rect()
        self._frame(rect)
        self._box_title(rect, "NAV-COM")

        font = fonts.font(20)
        line_h = font.get_height() + 4
        pad = 22
        rows = [
            ("POS", f"X {int(ship.pos_x):+06d}   Y {int(ship.pos_y):+06d}"),
            ("GRID", self.grid_ref(ship.pos_x, ship.pos_y)),
            ("VEL", f"X {ship.dir_x:+05.1f}   Y {ship.dir_y:+05.1f}"),
            ("SPD", f"{ship.speed:03.0f} / {SHIP_MAX_SPEED:03d} U"),
            ("HDG", f"{int(ship.heading) % 360:03d} DEG"),
        ]
        label_w = max(font.size(label)[0] for label, _ in rows) + 24
        top = rect.top + 28 + max(0, (rect.height - 36 - len(rows) * line_h) // 2)  # 28: below the title line
        for i, (label, value) in enumerate(rows):
            y = top + i * line_h
            self.screen.blit(font.render(label, True, theme.AMBER_DIM), (rect.left + pad, y))
            self.screen.blit(font.render(value, True, theme.GREEN), (rect.left + pad + label_w, y))

    HEADING_LEN = 110  # px the heading vector reaches from the ship
    SPEED_LEN = 150  # px the velocity vector reaches at SHIP_MAX_SPEED

    def _arrow(self, start, end, color, width=2, head=10):
        """A line from start to end with an arrowhead at end."""
        pygame.draw.line(self.screen, color, start, end, width)
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        base = (end[0] - ux * head, end[1] - uy * head)
        wing = (-uy * head * 0.5, ux * head * 0.5)
        pygame.draw.polygon(self.screen, color, [
            end,
            (base[0] + wing[0], base[1] + wing[1]),
            (base[0] - wing[0], base[1] - wing[1]),
        ])

    def draw_ship_vectors(self, ship, camera_x, camera_y, show=True):
        """Overlay on the ship in the flight window: a heading vector (where the nose
        points) and a velocity vector (where and how fast it is moving), each with a label.
        The heading vector has a fixed length; the velocity vector grows with speed."""
        if not show:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        cx = ship.rect.center[0] - camera_x
        cy = ship.rect.center[1] - camera_y
        clip = pygame.Rect(world_left, world_top, world_right - world_left, world_bottom - world_top)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(clip)

        font = fonts.font(16)
        start_gap = 44  # start outside the ship sprite

        # Heading: where the nose points
        fx, fy = ship.facing()
        hdg_start = (cx + fx * start_gap, cy + fy * start_gap)
        hdg_end = (cx + fx * (start_gap + self.HEADING_LEN), cy + fy * (start_gap + self.HEADING_LEN))
        self._arrow(hdg_start, hdg_end, theme.AMBER_BRIGHT)
        label = font.render(f"HDG {int(ship.heading) % 360:03d}", True, theme.AMBER_BRIGHT)
        self.screen.blit(label, label.get_rect(midbottom=(hdg_end[0], hdg_end[1] - 6)))

        # Velocity: where it is moving, length = speed
        if ship.speed > 1:
            ux, uy = ship.dir_x, ship.dir_y
            length = self.SPEED_LEN * min(1.0, ship.speed / SHIP_MAX_SPEED)
            vel_start = (cx + ux * start_gap, cy + uy * start_gap)
            vel_end = (cx + ux * (start_gap + length), cy + uy * (start_gap + length))
            self._arrow(vel_start, vel_end, theme.GREEN_BRIGHT)
            label = font.render(f"SPD {ship.speed:03.0f} U", True, theme.GREEN_BRIGHT)
            anchor = (vel_end[0] + 8, vel_end[1] + 8)
            self.screen.blit(label, label.get_rect(topleft=anchor))

        self.screen.set_clip(old_clip)

    def draw_ui_layout(self, show=True):
        """Draw UI panel backgrounds and borders with clean CRT chassis framing."""
        if not show:
            return
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

    def _callsign_rect(self):
        """The pilot ID box: top-left of the top panel."""
        return pygame.Rect(24, 22, 380, self.THIN_HEIGHT - 44)

    def draw_callsign_plate(self, callsign, player_id, pilots_on_net, local, show=True):
        """Pilot ID readout: callsign, IFF code and link status, in the same
        framed-box style as ship telemetry."""
        if not show:
            return
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

    def draw_power_readout(self, ship, show=True):
        """Fuel and current draw, right-aligned in the top panel opposite the pilot ID."""
        if not show:
            return
        top = self._get_panel_rects()[0]
        font = fonts.font(26)
        line_h = font.get_height() + 6

        # The frame is exactly as wide as the radar beneath it; everything inside is fitted to that width.
        radar_x, _, radar_size = self._get_radar_bounds()
        PAD, GAP, ACK_W = 16, 16, 170
        alert_font = fonts.font(20)
        box_h = 2 * line_h + 14 + alert_font.get_height() + 20 + 12  # frame: 12 above the block, to the alert row's bottom
        y = top.centery - box_h // 2 + 12  # so the frame is centred in the top panel
        alert_y = y + 2 * line_h + 14
        panel_box = pygame.Rect(radar_x, y - 12, radar_size, box_h)
        self._frame(panel_box, fill=theme.BG, tick=10, width=1)

        # Top rows: [fault button] then label / bar / value columns filling the rest
        x_val = panel_box.right - PAD
        val_w = font.size("0000")[0]
        lab_w = font.size("DRAW")[0]
        x_lab = panel_box.left + PAD + ACK_W + GAP
        x_bar = x_lab + lab_w + GAP
        bar_w = x_val - val_w - GAP - x_bar
        BAR_CELLS = max(4, (bar_w - font.size("||")[0]) // font.size("#")[0])  # as many cells as fit
        self._power_rect = pygame.Rect(x_lab, y, x_val - x_lab, 2 * line_h)  # the whole block, for overlays

        fuel = max(0, min(SHIP_MAX_FUEL, ship.fuel))
        filled = round(BAR_CELLS * fuel / SHIP_MAX_FUEL)
        frac = fuel / SHIP_MAX_FUEL
        bar_col = theme.RED if frac < 0.2 else (theme.AMBER_BRIGHT if frac < 0.4 else theme.GREEN)
        bar = font.render(f"|{'#' * filled}{' ' * (BAR_CELLS - filled)}|", True, bar_col)

        self.screen.blit(font.render("FUEL", True, theme.AMBER_DIM), (x_lab, y))
        self.screen.blit(bar, (x_bar, y))
        self._fuel_bar_rect = pygame.Rect(x_bar, y, bar.get_width(), bar.get_height())  # for the depleted card
        self._throttle_rect = pygame.Rect(x_bar, y + line_h, bar.get_width(), font.get_height())  # DRAW row, under the bar
        fuel_val = font.render(f"{int(fuel):04d}", True, bar_col)
        self.screen.blit(fuel_val, fuel_val.get_rect(topright=(x_val, y)))

        self.screen.blit(font.render("DRAW", True, theme.AMBER_DIM), (x_lab, y + line_h))
        draw_val = font.render(f"{ship.current_draw:.2f}", True, theme.GREEN)
        self.screen.blit(draw_val, draw_val.get_rect(topright=(x_val, y + line_h)))

        # Fault acknowledge: left of the readout, as tall as its two rows
        self._button(pygame.Rect(panel_box.left + PAD, y, ACK_W, 2 * line_h),
                     "FAULT ACK", 'fuel_acknowledge', lit=ship.fuel_acknowledge)

        if ship.fuel_acknowledge:
            return

        # Alerts on a row under the readout (clear of the out-of-fuel box, which ends 12px below the block)
        LOW_FUEL = SHIP_MAX_FUEL * LOW_FUEL_FRACTION  # 10% of the tank (matches LOW_FUEL_FRACTION)
        # current_draw at or above this is high
        # Each alert has a fixed slot so it never moves: LOW FUEL bottom-left, HIGH DRAW bottom-right.
        # A slot's box only appears while its alert is on; the words flash inside it.
        blink_on = (pygame.time.get_ticks() // 300) % 2 == 0
        slots = [
            (fuel <= LOW_FUEL, "LOW FUEL!", "left"),
            (ship.current_draw >= HIGH_USE, "WARNING, HIGH DRAW!", "right"),
        ]
        for active, text, side in slots:
            if not active:
                continue
            surf = alert_font.render(text, True, theme.RED)
            box = pygame.Rect(0, 0, surf.get_width() + 24, surf.get_height() + 12)
            if side == "left":
                box.topleft = (panel_box.left + PAD, alert_y)
            else:
                box.topright = (panel_box.right - PAD, alert_y)
            self._frame(box, theme.RED, fill=theme.BG, tick=8, width=2)
            if blink_on:
                self.screen.blit(surf, surf.get_rect(center=box.center))

    def draw_cloaking_level(self, ship, show=True):
        """Cloaking readout in the bottom console: how visible the ship is to others, as a
        percentage (100 = fully visible, 0 = hidden), plus five cells filled up to the cloaking
        level, with the CLOAK -/+ buttons either side.
        Reads the true ship.visibility, not the self-view floor, so 0% means enemies cannot see you."""
        if not show:
            return
        level = max(0, min(5, int(ship.cloaking_value)))
        visible_percent = round(map_to_range_linear(ship.visibility, 0, 255, 0, 100))
        rect = self._cloak_rect()
        self._frame(rect)
        self._box_title(rect, "CLOAKING")

        value = fonts.font(15).render(f"VISIBILITY: {visible_percent}%", True, theme.GREEN if visible_percent else theme.AMBER_DIM)
        self.screen.blit(value, value.get_rect(topright=(rect.right - 22, rect.top + 6)))

        # One row: DECLOAK | five level cells | CLOAK. The buttons register their own clicks.
        pad, gap = 22, 12
        btn_w = btn_h = 48  # square
        row_top = rect.centery - btn_h // 2 + 12
        self._button(pygame.Rect(rect.left + pad, row_top, btn_w, btn_h), "-", "cloak_down",
                     enabled=level > 0, font=fonts.font(26))
        self._button(pygame.Rect(rect.right - pad - btn_w, row_top, btn_w, btn_h), "+", "cloak_up",
                     enabled=level < 5, font=fonts.font(26))

        cells_left = rect.left + pad + btn_w + gap
        cells_right = rect.right - pad - btn_w - gap
        cell_gap = 8
        cell_w = (cells_right - cells_left - 4 * cell_gap) // 5
        cell_h = 22
        y = row_top + (btn_h - cell_h) // 2
        for i in range(5):
            cell = pygame.Rect(cells_left + i * (cell_w + cell_gap), y, cell_w, cell_h)
            if i < level:
                pygame.draw.rect(self.screen, theme.GREEN, cell)
            else:
                pygame.draw.rect(self.screen, theme.AMBER_DIM, cell, 2)

    def draw_ui_ftl_override(self, ftl_jumping, show=True):
        """Draw simple FTL JUMPING text boxes that fade out.

        Args:
            ftl_jumping: Boolean indicating if FTL jump is active
        """
        if not show:
            return
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

    def draw_world_grid(self, camera_x, camera_y, show_grid=True, show=True):
        """Draw coordinate grid overlay in world space.

        Args:
            camera_x: Camera X position
            camera_y: Camera Y position
            show_grid: Boolean to toggle grid on/off
        """
        if not show:
            return
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

    def draw_missile_lock_warning(self, locked, show=True):
        """Draw red blinking border around viewport when missile lock detected."""
        if not show:
            return
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

    def draw_laser_painted_warning(self, painted, show=True):
        """Draw flashing warning when ship is laser painted by enemy.

        Args:
            painted: Boolean indicating if ship is currently painted
        """
        if not show:
            return
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

    def draw_viewport_banner(self, text, color=None, show=True):
        """Large text centered at the top of the viewport, on a dark plate. Call it every
        frame the message should show. Keeps clear of the gun-solution banner (which sits
        higher up and is smaller) by starting a little lower."""
        if not show:
            return
        if not text:
            return
        world_left, world_right, world_top, _ = self._get_world_bounds()
        banner_font = fonts.font(44)
        line_color = color or theme.GREEN_BRIGHT
        max_width = (world_right - world_left) - 120
        lines = self._wrap_banner_text(text, banner_font, max_width)
        line_surfs = [banner_font.render(line, True, line_color) for line in lines]
        line_height = banner_font.get_linesize()
        block_width = max(surf.get_width() for surf in line_surfs)
        block_height = line_height * len(line_surfs)
        center_x = (world_left + world_right) // 2
        block_top = world_top + 60
        plate = pygame.Rect(0, 0, block_width, block_height).inflate(40, 16)
        plate.midtop = (center_x, block_top - 8)
        pygame.draw.rect(self.screen, theme.BLACK, plate)
        pygame.draw.rect(self.screen, line_color, plate, 2)
        for index, surf in enumerate(line_surfs):
            line_rect = surf.get_rect(midtop=(center_x, block_top + index * line_height))
            self.screen.blit(surf, line_rect)

    def _wrap_banner_text(self, text, banner_font, max_width):
        """Split `text` into lines no wider than `max_width` pixels, breaking on spaces.
        A single word wider than max_width gets its own line, unbroken."""
        lines = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split():
                candidate = word if not current else current + " " + word
                if banner_font.size(candidate)[0] <= max_width or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def display_ai_messages(self, messages, show=True):
        if not show:
            return
        world_left, _, world_top, _ = self._get_world_bounds()
        y = world_top + 10
        for message in messages[:5]:
            surf = self.font_body.render(message, True, theme.GREEN_BRIGHT)
            self.screen.blit(surf, (world_left + 10, y))
            y += surf.get_height() + 4

    def _radar_geometry(self):
        """(radar_rect, center_x, center_y, max_radius) of the radar scope."""
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        # Max radius is half the bounding box, not the full bounding box
        max_radius = radar_size // 2
        return (radar_rect, radar_rect.centerx, radar_rect.centery,
                max_radius)

    def draw_range_bands(self, hot, band_count, show=True):
        """Tint each distance band (1 = innermost, of `band_count`) in `hot` on the radar.
        Drawn after draw_radar, over the grid; faint enough to leave the blips readable."""
        if not show:
            return
        if not hot:
            return
        radar_rect, center_x, center_y, max_radius = self._radar_geometry()
        spacing = max_radius / band_count
        layer = getattr(self, '_band_layer', None)
        if layer is None or layer.get_size() != radar_rect.size:
            layer = self._band_layer = pygame.Surface(radar_rect.size, pygame.SRCALPHA)
        layer.fill((0, 0, 0, 0))
        local_center = (center_x - radar_rect.x, center_y - radar_rect.y)
        # Outermost first: each band's cut-out would otherwise erase the inner bands already drawn
        for i in sorted(hot, reverse=True):
            pygame.draw.circle(layer, theme.RANGE_BAND, local_center, round(spacing * i))
            if i > 1:
                pygame.draw.circle(layer, (0, 0, 0, 0), local_center, round(spacing * (i - 1)))
        old_clip = self.screen.get_clip()
        self.screen.set_clip(radar_rect)
        self.screen.blit(layer, radar_rect.topleft)
        self.screen.set_clip(old_clip)

    def draw_radar(self, player_ship, signatures, is_scanning=False, sweep_angle=None, rings=0, movers=(), show=True):
        """`rings` is how many distance rings to draw (0 for none). `movers` is (x, y) of each
        moving thing the close range scan sees: drawn as plain red dots, no heading."""
        if not show:
            return
        radar_rect, center_x, center_y, max_radius = self._radar_geometry()
        radar_x, radar_y, radar_size = radar_rect.x, radar_rect.y, radar_rect.width

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

        # Axis Crosshairs
        pygame.draw.line(self.screen, grid_color, (radar_x, center_y), (radar_x + radar_size, center_y), 1)
        pygame.draw.line(self.screen, grid_color, (center_x, radar_y), (center_x, radar_y + radar_size), 1)

        # Distance Rings
        if rings:
            ring_layer = pygame.Surface(radar_rect.size, pygame.SRCALPHA)
            for i in range(1, rings + 1):
                pygame.draw.circle(ring_layer, theme.RANGE_RING, (center_x - radar_x, center_y - radar_y),
                                   round(max_radius * i / rings), 1)
            self.screen.blit(ring_layer, radar_rect.topleft)

        # --- Out-of-bounds caution hatching: red diagonal lines wherever the map ends ---
        scale = max_radius / self.RADAR_SCALE
        px, py = player_ship.rect.center
        w_left = center_x + (0 - px) * scale
        w_right = center_x + (self.world_width - px) * scale
        w_top = center_y + (0 - py) * scale
        w_bottom = center_y + (self.world_height - py) * scale
        caution_red = (200, 30, 30)
        r = radar_rect
        strips = []
        if w_top > r.top:
            strips.append(pygame.Rect(r.left, r.top, r.width, min(r.height, int(w_top) - r.top)))
        if w_bottom < r.bottom:
            y0 = max(r.top, int(w_bottom))
            strips.append(pygame.Rect(r.left, y0, r.width, r.bottom - y0))
        if w_left > r.left:
            strips.append(pygame.Rect(r.left, r.top, min(r.width, int(w_left) - r.left), r.height))
        if w_right < r.right:
            x0 = max(r.left, int(w_right))
            strips.append(pygame.Rect(x0, r.top, r.right - x0, r.height))
        for strip in strips:
            self.screen.set_clip(strip.clip(r))
            for d in range(-r.height, r.width, 80):
                pygame.draw.line(self.screen, caution_red,
                                 (r.left + d, r.bottom), (r.left + d + r.height, r.top), 2)
        self.screen.set_clip(radar_rect)
        # Solid red boundary line at the world edge
        edge = pygame.Rect(int(w_left), int(w_top), int(w_right - w_left), int(w_bottom - w_top))
        pygame.draw.rect(self.screen, caution_red, edge, 2)

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

        # Moving contacts from the close range scan: a red dot where each one is now
        for mover_x, mover_y in movers:
            radar_px = int(center_x + (mover_x - player_x) * radar_scale)
            radar_py = int(center_y + (mover_y - player_y) * radar_scale)
            pygame.draw.circle(self.screen, theme.RED, (radar_px, radar_py), 3)

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

    def draw_radar_controls(self, is_scanning, show=True):
        """SWEEP button in the scope's top-right corner. Drawn after the laser and
        DFS lines so they don't cross it."""
        if not show:
            return
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        sweep = pygame.Rect(0, 0, 112, 34)
        sweep.topright = (radar_x + radar_size - 12, radar_y + 12)
        self._button(sweep, "SWEEP", 'radar_sweep', key="R", lit=is_scanning)

    def draw_laser(self, laser, laser_endpoint, camera_x, camera_y, active, show=True):
        if not show:
            return
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
        fx, fy = math.cos(rad), math.sin(rad)  # along the beam
        px, py = -fy, fx  # across the beam
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

    def draw_mining_beam(self, ship, rock, progress, camera_x, camera_y, show=True):
        """Mining beam from the ship to the rock it is burning. Drawn the same way as
        the pirate's beam (see DrawGame.draw_laser): layered beam with a pulsing impact
        ring on the rock. The rock's material and percentage sit beside it."""
        if not show:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        viewport = pygame.Rect(world_left, world_top,
                               world_right - world_left, world_bottom - world_top)
        self.screen.set_clip(viewport)

        sx = int(ship.center[0] - camera_x)
        sy = int(ship.center[1] - camera_y)
        ex = int(rock.pos_x - camera_x)
        ey = int(rock.pos_y - camera_y)

        # Same three layers as the pirate beam: glow, inner, hot core
        pygame.draw.line(self.screen, theme.RED_DIM, (sx, sy), (ex, ey), 8)
        pygame.draw.line(self.screen, theme.RED_BRIGHT, (sx, sy), (ex, ey), 4)
        pygame.draw.line(self.screen, theme.WHITE, (sx, sy), (ex, ey), 2)

        # Impact ring and crosshair, pulsing the same way the pirate's does
        pulse = (pygame.time.get_ticks() / 1000 * 3) % 1.0
        radius = int(4 + pulse * 12)
        alpha = int(255 * (1.0 - pulse))
        ring = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*theme.RED_BRIGHT, alpha), (20, 20), radius, 2)
        flare_size = 6 - int(pulse * 4)
        if flare_size > 0:
            pygame.draw.line(ring, (*theme.WHITE, alpha), (20 - flare_size, 20), (20 + flare_size, 20), 1)
            pygame.draw.line(ring, (*theme.WHITE, alpha), (20, 20 - flare_size), (20, 20 + flare_size), 1)
        self.screen.blit(ring, (ex - 20, ey - 20))

        label = self.font_scan_body.render(f"{rock.material.upper()} {progress * 100:.0f}%", True, theme.RED_BRIGHT)
        label_rect = label.get_rect(midleft=(ex + rock.size + 8, ey))
        label_rect.clamp_ip(viewport)
        pygame.draw.rect(self.screen, theme.BG, label_rect.inflate(6, 2))
        self.screen.blit(label, label_rect)

        self.screen.set_clip(None)

    def draw_laser_targeting_info(self, target_type: str, laser_assessor, enabled: bool, show=True):
        """Draw laser targeting assessment status below the radar panel.

        Args:
            target_type: String classification of the target
            laser_assessor: LaserAssessor object with lock info
            enabled: Boolean indicating if laser targeting is active
        """

        if not show:
            return
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

    def material_box_rect(self):
        """The free space under the laser assessor box, down to the bottom console."""
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        laser_y = radar_y + radar_size + 14
        laser_h = (self.screen.get_height() - self.THIN_HEIGHT - 12 - laser_y) // 2
        box_y = laser_y + laser_h + 14
        box_h = self.screen.get_height() - self.THIN_HEIGHT - 12 - box_y
        return pygame.Rect(radar_x, box_y, radar_size, box_h)

    def draw_material_assessment(self, assessor, show=True):
        """Material assessor box: what the beam is on, scan progress, and the last result.

        assessor: MaterialAssessor (reads .laser, .scanning, .scan_progress(), .result)
        """
        if not show:
            return
        box = self.material_box_rect()
        laser_target = assessor.laser_target()
        enabled = assessor.laser.on
        scanning = assessor.scanning is not None

        border_color = self.COLOR_HUD_AMBER if enabled else theme.AMBER_DIM
        self._frame(box, border_color, tick=8)

        header = self.font_tiny.render(" MATERIAL ASSESSMENT ", True, border_color)
        tab = header.get_rect(midleft=(box.left + 14, box.top))
        pygame.draw.rect(self.screen, theme.BG, tab)
        self.screen.blit(header, tab)

        top_h = box.height // 2

        # Status words, most specific first
        if not enabled:
            text_str, color = "ASSESSOR OFFLINE", theme.GREY
        elif scanning:
            text_str, color = "SCANNING TARGET", theme.AMBER_BRIGHT
        elif laser_target is None:
            text_str, color = "NO TARGET UNDER BEAM", theme.GREY
        elif assessor.result is not None and assessor.result[0] is laser_target:
            found = assessor.result[1].upper()
            # A bracketed result is an identification, not a material, so it gets no label
            if found.startswith("["):
                text_str, color = found, theme.RED_BRIGHT
            else:
                text_str, color = f"MATERIAL: {found}", self.COLOR_DATA
        else:
            text_str, color = "READY: PRESS SCAN", self.COLOR_HUD_AMBER

        region_top = box.top + tab.height // 2 + 2
        region = pygame.Rect(box.left + 8, region_top, box.width - 16, box.top + top_h - 22 - region_top)
        for size in (34, 30, 26, 22, 18, 14):
            status_font = fonts.font(size)
            surf = status_font.render(text_str, True, color)
            if status_font.get_height() <= region.height and surf.get_width() <= region.width:
                break
        self.screen.blit(surf, (region.left + 8, region.centery - surf.get_height() // 2))

        # Progress bar along the bottom of the top half: |###########     |
        # Segment count is worked out from the box width, so the bar runs edge to edge at the body font size.
        bar_font = self.font_scan_body
        cell_w = bar_font.size("#")[0]
        target_w = box.width - 28
        segments = max(1, (target_w - bar_font.size("||")[0]) // cell_w)
        filled = round(segments * assessor.scan_progress())
        bar_text = "|" + "#" * filled + " " * (segments - filled) + "|"
        bar_surf = bar_font.render(bar_text, True, self.COLOR_HUD_AMBER if scanning else theme.AMBER_DIM)
        self.screen.blit(bar_surf, bar_surf.get_rect(midleft=(box.left + 14, box.top + top_h - 14)))

    def draw_material_scan_button(self, assessor, show=True):
        """SCAN button in the bottom half of the material box. Drawn after the panel so it sits on top."""
        if not show:
            return
        box = self.material_box_rect()
        top_h = box.height // 2
        controls = pygame.Rect(box.left + 8, box.top + top_h + 4, box.width - 16, box.height - top_h - 8)
        can_scan = assessor.scanning is None and assessor.laser_target() is not None
        self._button_row(controls, [
            (1, "SCAN", 'material_scan', dict(key="N", enabled=can_scan)),
        ])

    def set_world(self, world):
        """The world the scene is showing: its size is what the radar and map are drawn to."""
        self.world_width, self.world_height = world.width, world.height

    def grid_ref(self, x, y):
        """Grid cell containing a world position, as '<col>X <row>Y' (clamped to the world)."""
        col = min(max(int(x // GRID_SIZE), 0), self.world_width // GRID_SIZE - 1)
        row = min(max(int(y // GRID_SIZE), 0), self.world_height // GRID_SIZE - 1)
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

    def marker_from_click(self, marker_mode):
        """(shape, world_x, world_y) for the latest map click, placed with marker_mode.

        None when marker_mode is not a shape or no button-hit click has happened yet.
        """
        click = self.buttons.last_click_pos
        if marker_mode not in self.MARKER_SHAPES or click is None:
            return None
        wx, wy = self.map_screen_to_world(click)
        return (marker_mode, wx, wy)

    # Hull hits: (seconds the picture takes to settle back, strength at the hit)
    IMPACT_ASTEROID = (0.7, 0.5)
    IMPACT_MISSILE = (3.5, 0.9)

    def impact_asteroid(self):
        crt.impact(*self.IMPACT_ASTEROID)

    def impact_missile(self):
        crt.impact(*self.IMPACT_MISSILE)

    def set_hull_damage(self, health):
        """The picture's tearing follows the hull: clean at full health, worst at zero."""
        crt.set_damage(health)

    def draw_pause_console(self, pause, underlay=True, show=True):
        """The operator console over whatever the scene has drawn so far."""
        if not show:
            return
        pause.draw(self.screen, self.buttons, underlay=underlay)

    def view_size(self):
        """Size of the screen the world is drawn to, in pixels."""
        return self.screen.get_size()

    def draw_tactical_map(self, active, player_ship, confirmed_contacts, scan_active=False, scan_range=1000, laser_active=False, laser_direction=0, laser_locked=False, locked_object=None, markers=(),
                          marker_mode=None, show=True):
        """marker_mode: None, 'PICK' (choosing a shape) or a shape name (waiting for a click on the map)."""
        if not show:
            return
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
        max_x = min(self.world_width, int((player_x + view_margin) // GRID_SIZE + 1) * GRID_SIZE)
        min_y = max(0, int((player_y - view_margin) // GRID_SIZE) * GRID_SIZE)
        max_y = min(self.world_height, int((player_y + view_margin) // GRID_SIZE + 1) * GRID_SIZE)

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
            world_to_screen(self.world_width - player_x, 0 - player_y),
            world_to_screen(self.world_width - player_x, self.world_height - player_y),
            world_to_screen(0 - player_x, self.world_height - player_y)
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

    REPLAY_PILOT_COLORS = (theme.GREEN, theme.AMBER_BRIGHT, theme.RED_BRIGHT, theme.WHITE, theme.GREEN_BRIGHT)

    def draw_replay_map(self, asteroids, pilots, world_width, world_height, progress, playing, last_sample, show=True):
        """After-action replay: the whole world with every asteroid as a circle, and each
        pilot's recorded flight drawn up to `progress` (in samples, see ReplayState).
        pilots: [(callsign, [(x, y), ...]), ...]. The control buttons are registered here
        with replay_* actions, which MainScene routes."""
        if not show:
            return
        w, h = self.screen.get_size()
        x0 = 40
        head = self.menu_small_font
        body = self.menu_font

        top = 32
        self.screen.blit(head.render("ERGOT SYSTEMS // FLIGHT REPLAY", True, theme.AMBER_DIM), (x0, top))
        elapsed = int(progress * POSITION_RECORD_SECONDS)
        clock = head.render(f"T+ {elapsed // 60:02d}:{elapsed % 60:02d}", True, theme.AMBER_BRIGHT)
        self.screen.blit(clock, clock.get_rect(topright=(w - x0, top)))
        rule_y = top + head.get_height() + 10
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (x0, rule_y), (w - x0, rule_y))

        # Legend: one line per pilot, in the colour of its path
        legend_w = 260
        y = rule_y + 24
        for i, (callsign, _) in enumerate(pilots):
            color = self.REPLAY_PILOT_COLORS[i % len(self.REPLAY_PILOT_COLORS)]
            mid = y + body.get_height() // 2
            pygame.draw.line(self.screen, color, (x0, mid), (x0 + 24, mid), 3)
            self.screen.blit(body.render(callsign.upper(), True, color), (x0 + 36, y))
            y += body.get_height() + 10

        map_left = x0 + legend_w + 24
        map_rect = pygame.Rect(map_left, rule_y + 24, w - map_left - x0, h - rule_y - 24 - 110)
        pygame.draw.rect(self.screen, self.COLOR_DFS_BG, map_rect)

        # The whole world fits the panel, centred, at one scale on both axes
        scale = min(map_rect.width / world_width, map_rect.height / world_height)
        origin_x = map_rect.left + (map_rect.width - world_width * scale) / 2
        origin_y = map_rect.top + (map_rect.height - world_height * scale) / 2

        def to_screen(wx, wy):
            return origin_x + wx * scale, origin_y + wy * scale

        previous_clip = self.screen.get_clip()
        self.screen.set_clip(map_rect)

        pygame.draw.rect(self.screen, theme.AMBER_DIM,
                         (int(origin_x), int(origin_y), int(world_width * scale), int(world_height * scale)), 1)

        for asteroid in asteroids:
            centre = to_screen(asteroid.pos_x, asteroid.pos_y)
            pygame.draw.circle(self.screen, theme.ASTEROID, (int(centre[0]), int(centre[1])),
                               max(1, int(asteroid.size * scale)), 1)

        for i, (_, path) in enumerate(pilots):
            color = self.REPLAY_PILOT_COLORS[i % len(self.REPLAY_PILOT_COLORS)]
            runs, gaps = self._track_runs(path, progress)
            for run in runs:
                points = [to_screen(x, y) for x, y in run]
                if len(points) >= 2:
                    pygame.draw.lines(self.screen, color, False, points, 2)
            for before, after in gaps:
                self._draw_blink_mark(to_screen(*before), color)
                if after is not None:
                    self._draw_blink_mark(to_screen(*after), color)
                    self._draw_dashed_line(to_screen(*before), to_screen(*after), color)
            if runs and runs[-1]:
                head_x, head_y = to_screen(*runs[-1][-1])
                pygame.draw.circle(self.screen, color, (int(head_x), int(head_y)), 4)

        self.screen.set_clip(previous_clip)
        self._frame(map_rect, self.COLOR_DFS_BORDER, fill=None, width=2, tick=14)

        # Controls under the map. Each is greyed out when it would do nothing.
        specs = [
            (1, "BACK", 'replay_back', dict(key="LEFT", enabled=progress > 0)),
            (1, "PAUSE" if playing else "PLAY", 'replay_play', dict(key="SPACE", enabled=last_sample > 0)),
            (1, "STEP", 'replay_forward', dict(key="RIGHT", enabled=progress < last_sample)),
            (1, "EXIT REPLAY", 'replay_exit', dict(key="ESC")),
        ]
        row = pygame.Rect(map_rect.left, map_rect.bottom + 20, map_rect.width, 40)
        self._button_row(row, specs)

    @staticmethod
    def _track_runs(path, progress):
        """A recorded path up to `progress` samples, as (runs, gaps).

        runs: lists of points to join with lines. A blink mark ends a run, so nothing is
        drawn across it. The last point of the final run is interpolated between the two
        samples the progress falls between.
        gaps: one (before, after) pair per blink. before is the last point before the jump,
        after the first point past it. after is None until the progress reaches it.
        """
        if not path:
            return [], []
        whole = min(int(progress), len(path) - 1)
        runs, gaps = [], []
        run = []
        for point in path[:whole + 1]:
            if point == BLINK_RECORD_MARK:
                if run:
                    runs.append(run)
                    gaps.append((run[-1], None))
                    run = []
                continue
            if gaps and gaps[-1][1] is None and not run:
                gaps[-1] = (gaps[-1][0], point)
            run.append(point)

        fraction = progress - whole
        ahead = path[whole + 1] if whole + 1 < len(path) else None
        if fraction > 0 and run and ahead is not None and ahead != BLINK_RECORD_MARK:
            (x0, y0), (x1, y1) = path[whole], ahead
            run.append((x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction))
        if run:
            runs.append(run)
        return runs, gaps

    def _draw_blink_mark(self, centre, color, size=5):
        cx, cy = int(centre[0]), int(centre[1])
        pygame.draw.line(self.screen, color, (cx - size, cy - size), (cx + size, cy + size), 2)
        pygame.draw.line(self.screen, color, (cx - size, cy + size), (cx + size, cy - size), 2)

    def _draw_dashed_line(self, start, end, color, dash=6, gap=5):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if length == 0:
            return
        dx, dy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
        distance = 0.0
        while distance < length:
            seg_end = min(distance + dash, length)
            a = (start[0] + dx * distance, start[1] + dy * distance)
            b = (start[0] + dx * seg_end, start[1] + dy * seg_end)
            pygame.draw.line(self.screen, color, a, b, 1)
            distance += dash + gap

    def draw_catastrophe_warning(self, active, show=True):
        """Draw subtle catastrophe alert - pulsing red border and corner X.

        Args:
            active: Boolean indicating if catastrophe warning is active
        """
        if not show:
            return
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

    def draw_dfs_warning(self, active, on, timer=0.0, show=True):
        """Draw pulsing scan sweep when being swept by DFS.

        Args:
            active: Boolean indicating if warning should display
            timer: Current timer value (0-3 seconds). Caller handles incrementing.
            :param on:
        """
        if not show:
            return
        if not active:
            return

        if not on:
            return

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        # Corner warning indicator (top right; the top left one is gone)
        indicator_color = theme.RED
        indicator_size = 8
        pygame.draw.circle(self.screen, indicator_color, (world_right - 15, world_top + 15), indicator_size, 2)

        # Plain text in a red box, fixed at the top-left of the viewport
        warning_font = fonts.legacy_font(28)
        warning_text = warning_font.render("STATUS: DFS SWEEP DETECTED", True, theme.RED)
        pad = 10
        box = pygame.Rect(world_left + 32, world_top + 30,
                          warning_text.get_width() + pad * 2, warning_text.get_height() + pad * 2)
        pygame.draw.rect(self.screen, theme.BG, box)
        pygame.draw.rect(self.screen, theme.RED, box, 2)
        self.screen.blit(warning_text, (box.left + pad, box.top + pad))

    def draw_missile_contact(self, time_left, duration=1.5, show=True):
        """Banner at the top of the viewport confirming a missile reached its contact.

        Args:
            time_left: Seconds remaining (counts down to 0). Caller handles the timer.
            duration: Total display time, used to compute the fade.
        """
        if not show:
            return
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

    def draw_ship_destroyed(self, time_left, duration, callsign, show=True):
        """Banner across the top of the viewport for a couple of seconds when another
        pilot's ship goes down. Flickers in and out, like the missile contact banner."""
        if not show:
            return
        if time_left <= 0:
            return

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        elapsed = duration - time_left
        if elapsed < 0.2 and int(elapsed * 30) % 2:
            return
        if time_left < duration / 4 and int(time_left * 12) % 2:
            return

        text = self.font_scan_header.render(f"SHIP DESTRUCTION DETECTED: {callsign}", True, theme.RED)
        pad_x, pad_y = 18, 8
        box = pygame.Rect(0, 0, text.get_width() + pad_x * 2, text.get_height() + pad_y * 2)
        box.midtop = ((world_left + world_right) // 2, world_top + 16)
        self._frame(box, theme.RED, fill=theme.BG, tick=6)
        self.screen.blit(text, (box.left + pad_x, box.top + pad_y))

    def _deep_field_rect(self):
        """The deep field scan readout: the left-hand box in the bottom console."""
        return self._readout_rects()[0]

    def draw_deep_field_panel(self, has_result, reported_range, direction_index, system_online=True, show=True):
        if not show:
            return
        rect = self._deep_field_rect()
        panel_x, panel_y, panel_width, panel_height = rect
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
        # --- Status and the last scan's reading ---
        y = rect.top + 28
        if not system_online:
            self.screen.blit(self.font_scan_body.render("STATUS: OFFLINE", True, self.COLOR_DFS_GRAY), (x, y))
            reading, color = "NO SIGNAL", self.COLOR_DFS_GRAY
        else:
            self.screen.blit(self.font_scan_body.render("STATUS: ONLINE", True, self.COLOR_DFS_GREEN), (x, y))
            if not has_result:
                reading, color = "AWAITING SCAN", self.COLOR_DFS_GRAY
            elif reported_range is None:
                reading, color = "NO MOVEMENT", self.COLOR_DFS_GRAY
            else:
                reading, color = f"ENEMY MOVEMENT ~{int(round(reported_range, -1))} U", self.COLOR_DFS_RED
        self.screen.blit(self.font_scan_body.render(reading, True, color), (x, y + 34))

        controls = pygame.Rect(panel_x + 15, rect.bottom - 15 - 42, panel_width - 30, 42)
        self._button_row(controls, [
            (2, "< BRG", 'dfs_bearing_ccw', dict(key="DN", enabled=system_online)),
            (2, "BRG >", 'dfs_bearing_cw', dict(key="UP", enabled=system_online)),
            (3, "RUN SCAN", 'dfs_scan', dict(key="O", enabled=system_online)),
            (2, "PWR", 'toggle_dfs', dict(key="K", lit=system_online)),
        ])

    def draw_dfs_corridor(self, player_ship, dfs_direction_index, camera_x, camera_y, active=False, show=True):
        if not show:
            return
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

        def arrow(cx, cy, length, head, width, color, line_w):
            """Arrow from (cx,cy) pointing along the scan heading."""
            tx, ty = cx + forward_x * length, cy + forward_y * length
            pygame.draw.line(self.screen, color, (cx, cy), (tx, ty), line_w)
            bx, by = tx - forward_x * head, ty - forward_y * head
            pygame.draw.polygon(self.screen, color, [
                (tx, ty),
                (bx - perp_x * width, by - perp_y * width),
                (bx + perp_x * width, by + perp_y * width)])

        # --- 1. World Viewport: indicator on the ship ---
        viewport = pygame.Rect(world_left, world_top, world_right - world_left, world_bottom - world_top)
        self.screen.set_clip(viewport)

        # Faint baseline so the sweep edge is still visible
        pygame.draw.line(self.screen, orange_color,
                         (start_x - camera_x, start_y - camera_y), (end_x - camera_x, end_y - camera_y), 1)

        sx, sy = origin_x - camera_x, origin_y - camera_y
        h = max(player_ship.rect.width, player_ship.rect.height) * 0.5 + 10

        def pt(f, p):
            return (sx + forward_x * f + perp_x * p, sy + forward_y * f + perp_y * p)

        # Two parallel arrows flanking the ship, pointing along the scan heading
        for side in (-1, 1):
            p = side * h
            pygame.draw.line(self.screen, amber_color, pt(-h, p), pt(h, p), 2)
            pygame.draw.lines(self.screen, amber_color, False,
                              [pt(h - 8, p - side * 7), pt(h + 2, p), pt(h - 8, p + side * 7)], 2)

        self.screen.set_clip(None)

        # --- 2. Radar Panel: baseline plus one clear heading arrow ---
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2
        radar_scale = radar_size / self.RADAR_SCALE

        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        self.screen.set_clip(radar_rect)

        radar_start = (center_x + (start_x - origin_x) * radar_scale,
                       center_y + (start_y - origin_y) * radar_scale)
        radar_end = (center_x + (end_x - origin_x) * radar_scale,
                     center_y + (end_y - origin_y) * radar_scale)
        pygame.draw.line(self.screen, orange_color, radar_start, radar_end, 1)

        # Large arrow from the ship to the radar edge, in the scan direction
        arrow(center_x, center_y, radar_size * 0.12, 8, 5, amber_color, 2)

        self.screen.set_clip(None)

    def draw_corpo_miner_fire_warning(self, pirate_firing, show=True):
        """Draw a single orange line sweeping left to right across viewport.

        Args:
            pirate_firing: Boolean indicating if pirates have lock and are firing
        """
        if not show:
            return
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

    def draw_bullet_damage_glitch(self, ship_took_damage, show=True):

        if not show:
            return
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

    def draw_out_of_fuel_warning(self, out_of_fuel, show=True):
        """Flashing red tag slotted over the fuel bar, only while the tank is empty."""
        if not show:
            return
        if not out_of_fuel or getattr(self, "_fuel_bar_rect", None) is None:
            return

        box = self._fuel_bar_rect.inflate(8, 8)

        # Hard blink between bright and dull red
        on = (pygame.time.get_ticks() // 350) % 2 == 0
        col = theme.RED_BRIGHT if on else theme.RED
        self._frame(box, col, fill=theme.BG, tick=10, width=2)

        title = fonts.font(20).render("DEPLETED", True, col)
        self.screen.blit(title, title.get_rect(center=box.center))

        # Systems throttled: a second tag in the free space under the bar, the largest size that fits
        if getattr(self, "_throttle_rect", None) is not None:
            tag = self._throttle_rect.inflate(8, 4)
            size = 18
            while size > 10 and fonts.font(size).size("SYSTEMS THROTTLED")[0] > tag.width - 8:
                size -= 1
            self._frame(tag, col, fill=theme.BG, tick=10, width=2)
            sub = fonts.font(size).render("SYSTEMS THROTTLED", True, col)
            self.screen.blit(sub, sub.get_rect(center=tag.center))

    def draw_low_health_warning(self, low_health, show=True):
        """Draw flashing red warning box in bottom left of viewport.

        Args:
            low_health: Boolean indicating if ship is at low health
        """
        if not show:
            return
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
