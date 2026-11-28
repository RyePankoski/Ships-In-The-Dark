import math
import random
import re
import zlib
from datetime import datetime, timezone

import pygame

from config import theme
from config import ui_constants as ui
from config import draw_ui_constants as k
from config.constants import (BLINK_RECORD_MARK, GRID_SIZE, HIGH_USE, LASER_RANGE, LOW_FUEL_FRACTION,
                              POSITION_RECORD_SECONDS, SHIP_MAX_FUEL, SHIP_MAX_SPEED, TOTAL_MISSILES)
from asset_handlers.buttons import ButtonLayer, draw_button, draw_frame
from asset_handlers.crt import crt
from asset_handlers.grime import build_panel
from asset_handlers.ui_scale import px, ui_font, ui_legacy_font
from simulation.settings import WorldSettings
from utility.geometry import map_to_range_linear
from utility.text_input import blink_cursor

LEADER_RE = re.compile(r"^(.*?)\.{3,}\s*(.*)$")  # "LABEL.......STATUS" boot lines


# Brightness factor for the boot and menu screens: a faint hum.
def _flicker(seconds):
    return 0.96 + math.sin(seconds * 35.0) * 0.02


def _lit(color, flicker):
    return tuple(int(v * flicker) for v in color)


def _utc_clock():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


class DrawUI:
    def __init__(self, screen):
        self.screen = screen
        self.world_width = self.world_height = WorldSettings().size  # set per match by set_world
        self.buttons = ButtonLayer()

        # Shared by the missile lock, laser painted and catastrophe flashes
        self.lock_blink_counter = 0
        self.pirate_sweep_counter = 0
        self.health_blink_counter = 0
        self.radiation_blink_counter = 0
        self.tutorial_splash_elapsed = 0.0

        # Filled in by the draw calls that own them, read by overlays drawn later
        self._panel_cache_key = None
        self._panel_cache = None
        self._band_layer = None
        self._fuel_bar_rect = None  # the fuel bar: the DEPLETED tag sits over it
        self._throttle_rect = None  # the free row under the bar: SYSTEMS THROTTLED sits there
        self._map_view = None  # (center, scale, player_x, player_y) of the last tactical map

    # ------------------------------------------------------------------
    # Shared drawing primitives
    # ------------------------------------------------------------------

    def _frame(self, rect, color=theme.AMBER, fill=theme.BG, tick=10, width=1):
        draw_frame(self.screen, rect, color, fill, tick=tick, width=width)

    # Draw a console button and register its click area in the same call.
    def _button(self, rect, label, action, key=None, lit=None, enabled=True, hold=False, **style):
        self.buttons.button(self.screen, rect, label, action, key=key, lit=lit, enabled=enabled, hold=hold, **style)

    def _button_row(self, rect, specs, gap=8):
        self.buttons.button_row(self.screen, rect, specs, gap=gap)

    # A box's name, as a heading line inside its top-left corner.
    def _box_title(self, rect, title, color=theme.AMBER, steady=False):
        font = ui_font(15)
        surf = (font.render_steady if steady else font.render)(title, True, color)
        self.screen.blit(surf, (rect.left + px(22), rect.top + px(6)))

    # A framed section with its name as a heading line inside the top.
    def _section(self, rect, title, frame=theme.AMBER_DIM, text=theme.AMBER):
        self._frame(rect, frame, fill=None, tick=8)
        self._box_title(rect, title, text)

    # A framed box whose title sits in a gap cut into its top border.
    # Returns the y where the box's contents can start.
    def _titled_box(self, rect, title, color=theme.AMBER_DIM, text=theme.AMBER):
        self._frame(rect, color, fill=None, tick=8, width=1)
        surf = ui_font(20).render(title, True, text)
        tab = pygame.Rect(rect.left + px(20), rect.top - surf.get_height() // 2,
                          surf.get_width() + px(16), surf.get_height())
        pygame.draw.rect(self.screen, theme.BG, tab)
        self.screen.blit(surf, (tab.left + px(8), tab.top))
        return rect.top + surf.get_height() // 2 + px(16)

    # A title sitting on the top border of a scope or instrument box, cut into the line.
    def _border_tab(self, rect, text, color, fill=theme.BG):
        surf = ui_legacy_font(k.FONT_SIZE_TINY).render(f" {text} ", True, color)
        tab = surf.get_rect(midleft=(rect.left + px(14), rect.top))
        pygame.draw.rect(self.screen, fill, tab)
        self.screen.blit(surf, tab)
        return tab

    # Render `texts` [(text, color), ...] side by side at the largest size that fits
    # `region` on one row. Falls back to the smallest size if nothing fits.
    def _fit_status(self, region, texts, gap=0):
        for size in (34, 30, 26, 22, 18, 14):
            font = ui_font(size)
            surfs = [font.render(text, True, color) for text, color in texts]
            width = sum(s.get_width() for s in surfs) + gap * (len(surfs) - 1)
            if font.get_height() <= region.height and width <= region.width:
                break
        return surfs

    # Two columns of label / value fields inside a box, one row per entry of `rows`.
    def _field_grid(self, box, rows, font, label_color, value_color):
        line_h = font.get_height() + px(12)
        col_w = box.width // 2
        for r, row in enumerate(rows):
            for c, (label, value) in enumerate(row):
                fx = box.left + px(22) + c * col_w
                fy = box.top + px(22 + k.BOX_HEAD) + r * line_h
                self.screen.blit(font.render(label, True, label_color), (fx, fy))
                self.screen.blit(font.render(value, True, value_color), (fx + px(220), fy))

    # One boxed field per setting, stacked from `top`. Stops before the bottom of the box.
    def _setting_lines(self, box, top, lines, color):
        font = ui_font(30)
        step = font.get_height() + px(22)
        for i, line in enumerate(lines):
            r = pygame.Rect(box.left + px(k.MENU_PAD), top + i * step, box.width - 2 * px(k.MENU_PAD), step - px(10))
            if r.bottom > box.bottom - px(k.MENU_PAD):
                break
            self._frame(r, theme.AMBER_FAINT, fill=None, tick=6, width=1)
            surf = font.render(line, True, color)
            self.screen.blit(surf, surf.get_rect(midleft=(r.left + px(18), r.centery)))

    # Up to two status lines under a box heading.
    def _status_lines(self, box, top, lines, color):
        font = ui_font(22)
        for i, line in enumerate(lines[:2]):
            self.screen.blit(font.render(line, True, color),
                             (box.left + px(k.MENU_PAD), top + px(4) + i * (font.get_height() + px(10))))

    # The identification line over a rule across the top of a panel. Returns the y below it.
    def _ident_strip(self, panel, x0, x1, font, color, rule_color):
        y = panel.top + px(18)
        ident = font.render(k.IDENT_LINE, True, color)
        self.screen.blit(ident, (x0, y))
        rev = font.render(k.REV_LINE, True, color)
        self.screen.blit(rev, rev.get_rect(topright=(x1, y)))
        y += ident.get_height() + px(8)
        pygame.draw.line(self.screen, rule_color, (x0, y), (x1, y), px(1))
        return y + px(16)

    # The callsign in large type under the box heading, with a rule beneath it.
    # Returns the y of the rule.
    def _draw_callsign_name(self, rect, name, color, rule_color):
        pad = px(22)
        big = ui_font(34)
        name_surf = big.render(name, True, color)
        if name_surf.get_width() > rect.width - 2 * pad:
            name_surf = ui_font(26).render(name, True, color)
        name_y = rect.top + px(8 + k.BOX_HEAD + 14)
        self.screen.blit(name_surf, (rect.left + pad, name_y))
        rule_y = name_y + big.get_height() + px(6)
        pygame.draw.line(self.screen, rule_color, (rect.left + pad, rule_y), (rect.right - pad, rule_y), px(1))
        return rule_y

    # ------------------------------------------------------------------
    # Geometry: where each panel sits on the screen
    # ------------------------------------------------------------------

    # The flight window, as (left, right, top, bottom).
    def _get_world_bounds(self):
        return (
            px(ui.PANEL_WIDTH),
            self.screen.get_width() - px(ui.PANEL_WIDTH),
            px(ui.THIN_HEIGHT),
            self.screen.get_height() - px(ui.THIN_HEIGHT),
        )

    def _viewport_rect(self):
        left, right, top, bottom = self._get_world_bounds()
        return pygame.Rect(left, top, right - left, bottom - top)

    # The four console panels around the flight window: (top, bottom, left, right).
    def _get_panel_rects(self):
        w, h = self.screen.get_size()
        panel_w, thin_h = px(ui.PANEL_WIDTH), px(ui.THIN_HEIGHT)
        return (
            pygame.Rect(0, 0, w, thin_h),
            pygame.Rect(0, h - thin_h, w, thin_h),
            pygame.Rect(0, thin_h, panel_w, h - 2 * thin_h),
            pygame.Rect(w - panel_w, thin_h, panel_w, h - 2 * thin_h),
        )

    # The radar scope, as (radar_x, radar_y, radar_size).
    def _get_radar_bounds(self):
        radar_x = self.screen.get_width() - px(ui.PANEL_WIDTH) + px(ui.RADAR_PADDING)
        radar_y = px(ui.THIN_HEIGHT) + px(ui.RADAR_PADDING)
        radar_size = self.screen.get_height() - 2 * px(ui.THIN_HEIGHT) - 2 * px(ui.RADAR_PADDING)
        # Leave room underneath for the laser target box and its buttons (14px gap + 70px box)
        radar_size = min(radar_size - px(84), px(ui.PANEL_WIDTH) - 2 * px(ui.RADAR_PADDING))
        return radar_x, radar_y, radar_size

    # (radar_rect, center_x, center_y, max_radius) of the radar scope.
    def _radar_geometry(self):
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        return radar_rect, radar_rect.centerx, radar_rect.centery, radar_size // 2

    # The control column: between the top and bottom consoles, inset from the edge.
    def _left_column_rect(self):
        m = px(ui.DFS_PANEL_MARGIN)
        return pygame.Rect(m, px(ui.THIN_HEIGHT) + m, px(ui.PANEL_WIDTH) - 2 * m,
                           self.screen.get_height() - 2 * px(ui.THIN_HEIGHT) - 2 * m)

    # The three readout boxes across the bottom console, right of the telemetry:
    # (deep field scan, nav-com, cloaking), equal width, sharing the strip's height.
    def _readout_rects(self):
        w, h = self.screen.get_size()
        top = h - px(ui.THIN_HEIGHT) + px(12)
        height = px(ui.THIN_HEIGHT - 24)
        left = px(ui.PANEL_WIDTH) + px(ui.DFS_PANEL_MARGIN)
        gap = px(12)
        slot_w = (w - px(ui.DFS_PANEL_MARGIN) - left - 2 * gap) // 3
        return [pygame.Rect(left + i * (slot_w + gap), top, slot_w, height) for i in range(3)]

    def _deep_field_rect(self):
        return self._readout_rects()[0]

    def _navcom_rect(self):
        return self._readout_rects()[1]

    def _cloak_rect(self):
        return self._readout_rects()[2]

    # The pilot ID box: top-left of the top panel.
    def _callsign_rect(self):
        return pygame.Rect(px(24), px(22), px(380), px(ui.THIN_HEIGHT - 44))

    # The laser assessor box: under the radar, half of the space down to the bottom console.
    def _laser_box_rect(self):
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        top = radar_y + radar_size + px(14)
        height = (self.screen.get_height() - px(ui.THIN_HEIGHT) - px(12) - top) // 2
        return pygame.Rect(radar_x, top, radar_size, height)

    # The free space under the laser assessor box, down to the bottom console.
    def material_box_rect(self):
        laser = self._laser_box_rect()
        box_y = laser.bottom + px(14)
        box_h = self.screen.get_height() - px(ui.THIN_HEIGHT) - px(12) - box_y
        return pygame.Rect(laser.left, box_y, laser.width, box_h)

    # ------------------------------------------------------------------
    # Full-screen pages: text screens, debrief, certificate
    # ------------------------------------------------------------------

    # A framed console, same style as the in-game operator console: header
    # strip, title, readout lines, a column of buttons
    # [(label, key hint, action) or (label, key hint, action, enabled)],
    # and a fault line (`footer`) or the input prompt along the bottom.
    def draw_text_screen(self, title, lines, footer="", header="", buttons=(), show=True):
        if not show:
            return
        self.buttons.begin_frame()
        w, h = self.screen.get_size()

        small = ui_font(k.MENU_SMALL_SIZE)
        title_surf = ui_font(k.MENU_TITLE_SIZE).render(title, True, theme.AMBER_BRIGHT)
        line_surfs = [ui_font(k.MENU_FONT_SIZE).render(line, True, theme.GREEN) for line in lines]
        footer_surf = small.render(footer, True, theme.RED) if footer else None

        btn_w, btn_h, btn_gap = px(360), px(50), px(12)

        # Plain fields on black, like the mission log: no card, one left margin
        x0 = px(k.PLAIN_MARGIN)
        top = px(k.PLAIN_TOP)
        header_surf = small.render(header.upper(), True, theme.AMBER_DIM)
        self.screen.blit(header_surf, (x0, top))
        rule_y = top + header_surf.get_height() + px(10)
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (x0, rule_y), (w - x0, rule_y), px(1))

        y = rule_y + px(40)
        self.screen.blit(title_surf, title_surf.get_rect(topleft=(x0, y)))
        y += title_surf.get_height() + px(36)
        for surf in line_surfs:
            self.screen.blit(surf, surf.get_rect(topleft=(x0, y)))
            y += surf.get_height() + px(12)
        if lines and buttons:
            y += px(24)
        for label, key, action, *rest in buttons:
            enabled = rest[0] if rest else True
            rect = pygame.Rect(x0, y, btn_w, btn_h)
            self._button(rect, label, action, key=key, enabled=enabled, align="left",
                         font=ui_font(k.MENU_FONT_SIZE), key_font=ui_font(k.MENU_KEY_SIZE))
            y += btn_h + btn_gap

        # Bottom line: the last fault if there is one, else the input prompt
        if footer_surf is None:
            footer_surf = small.render(f"STATUS: AWAITING INPUT {blink_cursor()}", True, theme.AMBER_DIM)
        self.screen.blit(footer_surf, footer_surf.get_rect(bottomleft=(x0, h - px(32))))

        self.buttons.end_frame()

    # End-of-mission readout: plain left-aligned fields on black, no frame.
    # options: [(action, label, key hint), ...], each an underlined clickable line.
    def draw_debrief_screen(self, status, detail, options, show=True):
        if not show:
            return
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        x0 = px(k.PLAIN_MARGIN)
        top = px(k.PLAIN_TOP)
        head = ui_font(k.MENU_SMALL_SIZE)
        body = ui_font(k.MENU_FONT_SIZE)

        self.screen.blit(head.render("ERGOT SYSTEMS // MISSION LOG", True, theme.AMBER_DIM), (x0, top))
        utc = head.render(f"UTC {_utc_clock()}", True, theme.AMBER_DIM)
        self.screen.blit(utc, utc.get_rect(topright=(w - x0, top)))
        rule_y = top + head.get_height() + px(10)
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (x0, rule_y), (w - x0, rule_y), px(1))

        line_h = body.get_height() + px(10)
        label_w = body.size("STATUS  ")[0]
        y = rule_y + px(24)
        for name, value, color in (("STATUS", status, theme.AMBER_BRIGHT), ("DETAIL", detail, theme.GREEN)):
            self.screen.blit(body.render(name, True, theme.AMBER_DIM), (x0, y))
            self.screen.blit(body.render(value, True, color), (x0 + label_w, y))
            y += line_h

        self.draw_options(options)

        self.buttons.end_frame()

    # A framed certificate of completion, centred, with two decorative buttons
    # (DOWNLOAD, PRINT) under it. The buttons are drawn but never registered, so they
    # do nothing when clicked.
    def draw_certificate(self, callsign, show=True):
        if not show:
            return
        w, h = self.screen.get_size()
        self.screen.fill(theme.BLACK)
        title_font = ui_font(k.MENU_TITLE_SIZE)
        body_font = ui_font(k.MENU_FONT_SIZE)
        small_font = ui_font(k.MENU_SMALL_SIZE)
        key_font = ui_font(k.MENU_KEY_SIZE)

        cert_w = min(px(860), w - px(80))
        cert_h = min(px(560), h - px(200))
        btn_h, btn_gap_y = px(50), px(24)
        group_top = (h - (cert_h + btn_gap_y + btn_h)) // 2
        cert = pygame.Rect(0, 0, cert_w, cert_h)
        cert.midtop = (w // 2, group_top)

        self._frame(cert, theme.AMBER, fill=theme.BLACK, tick=10, width=2)
        inner = cert.inflate(px(-24), px(-24))

        def centred(surf, y):
            self.screen.blit(surf, surf.get_rect(midtop=(cert.centerx, y)))
            return y + surf.get_height()

        y = centred(small_font.render("ERGOT SYSTEMS // FLIGHT TRAINING", True, theme.AMBER_DIM), inner.top + px(28))
        y = centred(title_font.render("CERTIFICATE OF COMPLETION", True, theme.AMBER_BRIGHT), y + px(20))
        rule_y = y + px(16)
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (cert.left + px(80), rule_y), (cert.right - px(80), rule_y), px(1))

        y = centred(small_font.render("THIS CERTIFIES THAT", True, theme.AMBER_DIM), rule_y + px(36))
        y = centred(title_font.render(callsign.upper(), True, theme.GREEN_BRIGHT), y + px(8))
        y = centred(body_font.render("has completed flight certification", True, theme.GREEN), y + px(20))
        y = centred(body_font.render("and is cleared to remote pilot class 42 drones", True, theme.GREEN), y + px(8))

        date_text = datetime.now().strftime("%Y-%m-%d")
        sign_y = inner.bottom - px(50)
        left_x = inner.left + px(70)
        right_x = inner.right - px(70)
        pygame.draw.line(self.screen, theme.AMBER_DIM, (left_x, sign_y), (left_x + px(240), sign_y), px(1))
        pygame.draw.line(self.screen, theme.AMBER_DIM, (right_x - px(240), sign_y), (right_x, sign_y), px(1))
        date_surf = small_font.render("DATE: " + date_text, True, theme.AMBER)
        self.screen.blit(date_surf, date_surf.get_rect(midbottom=(left_x + px(120), sign_y - px(6))))
        officer_surf = small_font.render("TRAINING OFFICER", True, theme.AMBER)
        self.screen.blit(officer_surf, officer_surf.get_rect(midbottom=(right_x - px(120), sign_y - px(6))))

        seal_center = (cert.centerx, sign_y - px(10))
        pygame.draw.circle(self.screen, theme.AMBER_DIM, seal_center, px(34), px(2))
        pygame.draw.circle(self.screen, theme.AMBER_FAINT, seal_center, px(26), px(1))

        btn_w, btn_gap = px(200), px(16)
        btn_y = cert.bottom + btn_gap_y
        total_w = btn_w * 2 + btn_gap
        left = w // 2 - total_w // 2
        for i, label in enumerate(("DOWNLOAD", "PRINT")):
            rect = pygame.Rect(left + i * (btn_w + btn_gap), btn_y, btn_w, btn_h)
            draw_button(self.screen, rect, label, align="center", font=body_font, key_font=key_font)

    # Underlined text options down the bottom-left: [(action, label, key hint or None), ...].
    def draw_options(self, options, show=True):
        if not show:
            return
        x0 = px(k.PLAIN_MARGIN)
        h = self.screen.get_height()
        body = ui_font(k.MENU_FONT_SIZE)
        head = ui_font(k.MENU_SMALL_SIZE)
        step = body.get_height() + px(14)
        first_y = h - px(48) - (len(options) - 1) * step
        for i, (action, label, key_hint) in enumerate(options):
            y = first_y + i * step
            text = body.render(label, True, theme.AMBER)
            key = head.render(f"  [{key_hint}]", True, theme.AMBER_DIM) if key_hint else pygame.Surface((0, 0))
            self.screen.blit(text, (x0, y))
            self.screen.blit(key, key.get_rect(bottomleft=(x0 + text.get_width(), y + text.get_height())))
            underline_y = y + text.get_height() + px(2)
            pygame.draw.line(self.screen, theme.AMBER_DIM, (x0, underline_y),
                             (x0 + text.get_width() + key.get_width(), underline_y), px(1))
            click = pygame.Rect(x0 - px(8), y - px(6),
                                text.get_width() + key.get_width() + px(16), text.get_height() + px(12))
            self.buttons.register(click, action)

    # ------------------------------------------------------------------
    # Framed menus: main menu, lobby, world settings
    # ------------------------------------------------------------------

    # The main menu, laid out like the boot screen: identification strip, a title,
    # a pilot-record field grid, a framed command grid, and a status block along the
    # bottom. `buttons` is [(label, key hint, action)].
    def draw_main_menu(self, title, callsign, buttons, footer="", show=True):
        if not show:
            return
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        flicker = _flicker(pygame.time.get_ticks() / 1000.0)
        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        TITLE = _lit(theme.AMBER_BRIGHT, flicker)
        LOG = _lit(theme.GREEN, flicker)
        FAULT = _lit(theme.RED_BRIGHT, flicker)

        field_font = ui_font(30)
        status_font = ui_font(22)
        btn_font = ui_font(30)
        key_font = ui_font(20)
        title_font = ui_font(64)
        small_font = ui_font(20)
        pad, gap = px(k.MENU_PAD), px(k.MENU_GAP)

        margin = px(k.MENU_MARGIN)
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)
        x0, x1 = panel.left + pad, panel.right - pad

        y = self._ident_strip(panel, x0, x1, small_font, HEAD, RULE)

        title_surf = title_font.render(title, True, TITLE)
        self.screen.blit(title_surf, (x0, y))
        y += title_surf.get_height() + px(26)

        line_h = field_font.get_height() + px(12)
        record = pygame.Rect(x0, y, x1 - x0, 2 * line_h + px(40 + k.BOX_HEAD))
        self._section(record, "PILOT RECORD")
        self._field_grid(record, [
            [("CALLSIGN", callsign or "-"), ("UNIT ID", "ITD-218562B")],
            [("MISSION", "SEEK AND DESTROY"), ("UTC", _utc_clock())],
        ], field_font, HEAD, LOG)
        y = record.bottom + gap

        # Status block pinned to the bottom of the frame; the command grid fills the rest
        status_h = px(120)
        status_box = pygame.Rect(x0, panel.bottom - pad - status_h, x1 - x0, status_h)
        command = pygame.Rect(x0, y, x1 - x0, status_box.top - gap - y)
        self._section(command, "COMMAND")
        btn_h, btn_gap = px(66), px(14)
        grid_h = len(buttons) * btn_h + (len(buttons) - 1) * btn_gap
        top = command.top + (command.height - grid_h) // 2
        for i, (label, key, action) in enumerate(buttons):
            rect = pygame.Rect(command.left + pad, top + i * (btn_h + btn_gap), command.width - 2 * pad, btn_h)
            self._button(rect, label, action, key=key, align="left", font=btn_font, key_font=key_font)

        self._section(status_box, "STATUS", HEAD, theme.AMBER)
        row_a = status_box.top + px(30 + k.BOX_HEAD)
        if footer:
            status_text, status_color = footer, FAULT
        else:
            status_text, status_color = f"STATUS: AWAITING INPUT {blink_cursor()}", TITLE
        self.screen.blit(status_font.render(status_text, True, status_color), (status_box.left + px(22), row_a))
        hint = status_font.render("SELECT BY KEY OR CLICK", True, HEAD)
        self.screen.blit(hint, hint.get_rect(topright=(status_box.right - px(22), row_a)))

        self.buttons.end_frame()

    # The flight lobby, in framed boxes: the pilot record and the pilots on the net on
    # top, the world parameters and the command buttons below, status along the bottom.
    # `roster` is [(player_id, callsign)] in order; `buttons` is [(label, key hint, action, enabled)].
    def draw_lobby_screen(self, callsign, your_id, roster, settings_lines, status_lines, buttons, show=True):
        if not show:
            return
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        flicker = _flicker(pygame.time.get_ticks() / 1000.0)
        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        TITLE = _lit(theme.AMBER_BRIGHT, flicker)
        LOG = _lit(theme.GREEN, flicker)
        LOG_HOT = _lit(theme.GREEN_BRIGHT, flicker)

        title_font = ui_font(64)
        field_font = ui_font(30)
        small_font = ui_font(22)
        btn_font = ui_font(30)
        key_font = ui_font(20)
        pad, gap = px(k.MENU_PAD), px(k.MENU_GAP)

        margin = px(k.MENU_MARGIN)
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)
        x0, x1 = panel.left + pad, panel.right - pad
        y = self._ident_strip(panel, x0, x1, ui_font(20), HEAD, RULE)
        title_surf = title_font.render("FLIGHT LOBBY", True, TITLE)
        self.screen.blit(title_surf, (x0, y))
        y += title_surf.get_height() + px(26)

        # Status block pinned to the bottom of the frame
        status_h = px(150)
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
        row_h = field_font.get_height() + px(18)
        value_x = record.left + pad + px(200)
        field_rect = pygame.Rect(value_x - px(14), top - px(4),
                                 record.right - pad - value_x + px(14), field_font.get_height() + px(12))
        self._frame(field_rect, theme.AMBER_DIM, fill=theme.BG, tick=6, width=1)
        self.screen.blit(field_font.render("CALLSIGN", True, HEAD), (record.left + pad, top))
        self.screen.blit(field_font.render(callsign + blink_cursor(), True, LOG_HOT), (value_x, top))
        for i, (label, value) in enumerate((("SLOT", f"{your_id:02d}"), ("PILOTS", f"{len(roster)} ON NET"))):
            yy = top + (i + 1) * row_h
            self.screen.blit(field_font.render(label, True, HEAD), (record.left + pad, yy))
            self.screen.blit(field_font.render(value, True, LOG), (value_x, yy))
        hint = small_font.render("ENTER TO CONFIRM", True, HEAD)
        self.screen.blit(hint, (record.left + pad, top + 3 * row_h + px(6)))

        # Pilots on the net: one box per pilot, yours highlighted, overflow as a count
        top = self._titled_box(roster_box, f"PILOTS ON NET  //  {len(roster)}")
        step = small_font.get_height() + px(22)
        capacity = max(0, (roster_box.bottom - pad - top) // step)
        shown = roster if len(roster) <= capacity else roster[:max(0, capacity - 1)]
        for i, (player_id, name) in enumerate(shown):
            r = pygame.Rect(roster_box.left + pad, top + i * step, roster_box.width - 2 * pad, step - px(8))
            mine = player_id == your_id
            self._frame(r, theme.GREEN if mine else theme.AMBER_FAINT, fill=None, tick=6, width=1)
            pid = small_font.render(f"{player_id:02d}", True, HEAD)
            self.screen.blit(pid, pid.get_rect(midleft=(r.left + px(18), r.centery)))
            name_surf = small_font.render(name, True, LOG_HOT if mine else LOG)
            self.screen.blit(name_surf, name_surf.get_rect(midleft=(r.left + px(84), r.centery)))
            if mine:
                tag = small_font.render("< YOU", True, LOG_HOT)
                self.screen.blit(tag, tag.get_rect(midright=(r.right - px(18), r.centery)))
        if len(roster) > len(shown):
            more = small_font.render(f"+{len(roster) - len(shown)} MORE", True, HEAD)
            self.screen.blit(more, (roster_box.left + pad, top + len(shown) * step + px(4)))

        # World parameters: one boxed field per setting
        top = self._titled_box(world, "WORLD PARAMETERS")
        self._setting_lines(world, top, settings_lines, LOG)

        # Command: the buttons, stacked and full width
        top = self._titled_box(command, "COMMAND")
        bh, bgap = px(66), px(14)
        total = len(buttons) * bh + (len(buttons) - 1) * bgap
        first = top + max(0, (command.bottom - pad - top - total) // 2)
        for i, (label, key, action, *rest) in enumerate(buttons):
            enabled = rest[0] if rest else True
            rect = pygame.Rect(command.left + pad, first + i * (bh + bgap), command.width - 2 * pad, bh)
            self._button(rect, label, action, key=key, enabled=enabled, font=btn_font, key_font=key_font)

        # Status
        top = self._titled_box(status_box, "STATUS", HEAD, theme.AMBER)
        self._status_lines(status_box, top, status_lines, LOG_HOT)
        hint = small_font.render("SELECT BY KEY OR CLICK", True, HEAD)
        self.screen.blit(hint, hint.get_rect(topright=(status_box.right - pad, top + px(4))))

        self.buttons.end_frame()

    # The world parameters screen, in the same framed-box layout as the lobby.
    # settings_lines: the current world, one line per setting. parameters: [(label, key
    # hint, action)] that each change one setting. back: (label, key hint, action).
    # notice_lines: the status block along the bottom.
    def draw_settings_screen(self, settings_lines, parameters, back, notice_lines, show=True):
        if not show:
            return
        self.buttons.begin_frame()
        w, h = self.screen.get_size()
        flicker = _flicker(pygame.time.get_ticks() / 1000.0)
        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        TITLE = _lit(theme.AMBER_BRIGHT, flicker)
        LOG = _lit(theme.GREEN, flicker)
        LOG_HOT = _lit(theme.GREEN_BRIGHT, flicker)

        title_font = ui_font(64)
        btn_font = ui_font(30)
        key_font = ui_font(20)
        pad, gap = px(k.MENU_PAD), px(k.MENU_GAP)

        margin = px(k.MENU_MARGIN)
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)
        x0, x1 = panel.left + pad, panel.right - pad
        y = self._ident_strip(panel, x0, x1, ui_font(20), HEAD, RULE)
        title_surf = title_font.render("WORLD SETTINGS", True, TITLE)
        self.screen.blit(title_surf, (x0, y))
        y += title_surf.get_height() + px(26)

        # Notice block pinned to the bottom of the frame
        status_h = px(150)
        status_box = pygame.Rect(x0, panel.bottom - pad - status_h, x1 - x0, status_h)

        # Left: the parameters to change. Right: the current world, then BACK.
        avail = status_box.top - gap - y
        left_w = int((x1 - x0 - gap) * 0.5)
        right_x = x0 + left_w + gap
        right_w = x1 - right_x
        command_h = px(150)
        world_h = avail - gap - command_h
        params = pygame.Rect(x0, y, left_w, avail)
        world = pygame.Rect(right_x, y, right_w, world_h)
        command = pygame.Rect(right_x, y + world_h + gap, right_w, command_h)

        # Parameters: one full-width button per setting
        top = self._titled_box(params, "PARAMETERS")
        bh, bgap = px(74), px(16)
        total = len(parameters) * bh + (len(parameters) - 1) * bgap
        first = top + max(0, (params.bottom - pad - top - total) // 2)
        for i, (label, key, action) in enumerate(parameters):
            rect = pygame.Rect(params.left + pad, first + i * (bh + bgap), params.width - 2 * pad, bh)
            self._button(rect, label, action, key=key, font=btn_font, key_font=key_font)

        top = self._titled_box(world, "CURRENT WORLD")
        self._setting_lines(world, top, settings_lines, LOG)

        # Command: BACK
        top = self._titled_box(command, "COMMAND")
        label, key, action = back
        rect = pygame.Rect(command.left + pad, top + max(0, (command.bottom - pad - top - px(66)) // 2),
                           command.width - 2 * pad, px(66))
        self._button(rect, label, action, key=key, font=btn_font, key_font=key_font)

        # Notice
        top = self._titled_box(status_box, "NOTICE", HEAD, theme.AMBER)
        self._status_lines(status_box, top, notice_lines, LOG_HOT)

        self.buttons.end_frame()

    # ------------------------------------------------------------------
    # Boot and training splashes
    # ------------------------------------------------------------------

    # Boot screen in the operator-console style: an identification strip, labelled
    # sections with left-aligned fields, a scrolling boot log with status words, and a
    # load block that states progress as numbers and text.
    def draw_splash_screen(self, enabled: bool, timer: float, show=True):
        if not show or not enabled:
            return

        w, h = self.screen.get_size()
        flicker = _flicker(timer)
        FRAME = theme.AMBER
        TITLE = _lit(theme.AMBER_BRIGHT, flicker)
        HEAD = theme.AMBER_DIM
        RULE = theme.AMBER_FAINT
        LOG = _lit(theme.GREEN, flicker)
        LOG_HOT = _lit(theme.GREEN_BRIGHT, flicker)
        FAULT = _lit(theme.RED_BRIGHT, flicker)

        ident_font = ui_font(20)
        field_font = ui_font(30)
        boot_font = ui_font(24)
        status_font = ui_font(22)

        # Same full-window panel and type scale as the main menu
        margin, pad = px(k.MENU_MARGIN), px(k.MENU_PAD)
        panel = pygame.Rect(margin, margin, w - 2 * margin, h - 2 * margin)
        self._frame(panel, FRAME, fill=theme.BG, tick=14, width=2)

        x0, x1 = panel.left + pad, panel.right - pad
        utc = _utc_clock()

        # Identification strip (small: operational data comes first)
        y = self._ident_strip(panel, x0, x1, ident_font, HEAD, RULE)

        # System identification: fixed two-column field grid
        line_h = field_font.get_height() + px(12)
        id_box = pygame.Rect(x0, y, x1 - x0, 3 * line_h + px(40 + k.BOX_HEAD))
        self._section(id_box, "SYSTEM IDENTIFICATION")
        self._field_grid(id_box, [
            [("UNIT ID", "ITD-218562B"), ("DEBUG REF", "218562B")],
            [("FIRMWARE", "4.7.2"), ("BUILD", "2026.11.21")],
            [("MISSION", "SEEK AND DESTROY"), ("UTC", utc)],
        ], field_font, HEAD, LOG)
        y = id_box.bottom + px(14)

        # Load block, pinned to the bottom of the frame
        load_h = px(130 + k.BOX_HEAD)
        load_box = pygame.Rect(x0, panel.bottom - px(18) - load_h, x1 - x0, load_h)

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

        # Boot log: label, dotted leader, status column. Scrolls like a terminal.
        log_box = pygame.Rect(x0, y, x1 - x0, load_box.top - px(14) - y)
        self._section(log_box, f"BOOT LOG  //  {len(lines)} ENTRIES")

        boot_lh = boot_font.get_height() + px(4)
        log_top = log_box.top + px(28 + k.BOX_HEAD)
        log_left = log_box.left + px(22)
        log_right = log_box.right - px(22)
        status_x = log_left + int((log_right - log_left) * 0.64)
        visible = max(1, (log_box.bottom - px(12) - log_top) // boot_lh)

        def line_start(i):
            return k.BOOT_START + i * k.BOOT_LINE_DELAY

        started = [i for i in range(len(lines)) if timer > line_start(i)]
        if started:
            last = started[-1]
            first = max(0, last - visible + 1)
            for row, i in enumerate(range(first, last + 1)):
                text = lines[i]
                chars = min(len(text), int((timer - line_start(i)) * k.BOOT_CHARS_PER_SECOND))
                y0 = log_top + row * boot_lh
                m = LEADER_RE.match(text)

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
                        label_end = log_left + boot_font.size(label)[0] + px(10)
                        for gx in range(label_end, status_x - px(10), px(9)):
                            pygame.draw.rect(self.screen, theme.AMBER_DIM, (gx, y0 + boot_lh - px(9), px(2), px(2)))
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
                    self.screen.blit(cur, (cursor_x + px(2), y0))

        # Load block: bar, numeric readout, explicit status text
        self._section(load_box, "LOAD SEQUENCE")

        total = len(lines) * k.BOOT_LINE_DELAY
        frac = min(1.0, max(0.0, (timer - k.BOOT_START) / total))
        faults = sum(1 for i in started if "FAILED" in lines[i])
        entries_done = len(started)

        bar = pygame.Rect(load_box.left + px(22), load_box.top + px(24 + k.BOX_HEAD), load_box.width - px(44), px(10))
        pygame.draw.rect(self.screen, theme.GREEN_FAINT, bar)
        pygame.draw.rect(self.screen, LOG, (bar.left, bar.top, int(bar.width * frac), bar.height))
        pygame.draw.rect(self.screen, HEAD, bar, px(1))

        def blit_seq(x, y, parts):
            for text, color in parts:
                surf = status_font.render(text, True, color)
                self.screen.blit(surf, (x, y))
                x += surf.get_width()

        row_a = bar.bottom + px(12)
        blit_seq(load_box.left + px(22), row_a, [
            (f"LOAD {int(frac * 100):3d}%", LOG),
            (f"   ENTRIES {entries_done:02d}/{len(lines):02d}", HEAD),
            (f"   FAULTS {faults:02d}", FAULT if faults else HEAD),
        ])

        if timer < k.BOOT_START:
            status_text, status_color = "STATUS: INITIALIZING", HEAD
        elif frac < 1.0:
            status_text, status_color = "STATUS: BOOTING", LOG
        elif faults:
            status_text, status_color = f"STATUS: READY, {faults} FAULT{'S' if faults != 1 else ''}", FAULT
        else:
            status_text, status_color = "STATUS: READY", TITLE

        row_b = row_a + status_font.get_height() + px(8)
        blit_seq(load_box.left + px(22), row_b, [(status_text, status_color)])

        if timer > k.BOOT_PROMPT_AFTER and int(timer * 2.5) % 2 == 0:
            msg = status_font.render("PRESS ENTER TO CONTINUE", True, TITLE)
        else:
            msg = status_font.render("INPUT: LOCKED", True, HEAD)
        self.screen.blit(msg, msg.get_rect(topright=(load_box.right - px(22), row_b)))

    # Call every frame with the frame time. Returns True once the splash has run its course.
    def draw_tutorial_splash(self, dt):
        self.tutorial_splash_elapsed += dt
        progress = min(1.0, self.tutorial_splash_elapsed / k.TUTORIAL_SPLASH_SECONDS)

        w, h = self.screen.get_size()
        self.screen.fill(theme.BLACK)
        panel = pygame.Rect(px(16), px(16), w - px(32), h - px(32))
        self._frame(panel, theme.AMBER, fill=theme.BG, tick=14, width=2)

        title = ui_font(k.MENU_TITLE_SIZE).render("ERGOT SYSTEMS TRAINING MODULE", True, theme.AMBER_BRIGHT)
        title_rect = title.get_rect(midtop=(panel.centerx, panel.top + px(28)))
        self.screen.blit(title, title_rect)

        view_top = title_rect.bottom + px(20)
        view = pygame.Rect(panel.left + px(28), view_top, panel.width - px(56), panel.bottom - px(70) - view_top)
        self._frame(view, theme.AMBER_DIM, fill=theme.BLACK, tick=8)

        cx, cy = view.center
        ring_rx = int(min(view.width, view.height) * 0.36)
        ring_ry = int(ring_rx * 0.45)

        self._draw_splash_ring_half((cx, cy), ring_rx, ring_ry, 180, theme.AMBER_DIM)
        self._draw_splash_ring_half((cx, cy), ring_rx, ring_ry, 0, theme.AMBER)

        # The ship flies one lap outside the ring, starting at the near side, nose along its path
        orbit_rx = ring_rx * k.TUTORIAL_SPLASH_ORBIT_SCALE
        orbit_ry = ring_ry * k.TUTORIAL_SPLASH_ORBIT_SCALE
        angle = math.radians(90 + 360 * progress)
        position = (cx + orbit_rx * math.cos(angle), cy + orbit_ry * math.sin(angle))
        travel_x = -orbit_rx * math.sin(angle)
        travel_y = orbit_ry * math.cos(angle)
        travel_length = math.hypot(travel_x, travel_y)
        self._draw_splash_ship(position, (travel_x / travel_length, travel_y / travel_length))

        filled = int(k.TUTORIAL_SPLASH_BAR_LENGTH * progress)
        bar_text = "|" + ("#" * filled).ljust(k.TUTORIAL_SPLASH_BAR_LENGTH) + "|"
        bar = ui_font(k.MENU_FONT_SIZE).render(bar_text, True, theme.AMBER)
        self.screen.blit(bar, bar.get_rect(midtop=(panel.centerx, view.bottom + px(12))))

        return self.tutorial_splash_elapsed >= k.TUTORIAL_SPLASH_SECONDS

    # One half of the ring as an elliptical arc. 0 is the near half, 180 the far half.
    def _draw_splash_ring_half(self, center, rx, ry, start_degrees, color):
        points = []
        for degrees in range(start_degrees, start_degrees + 181, 5):
            radians = math.radians(degrees)
            points.append((center[0] + rx * math.cos(radians), center[1] + ry * math.sin(radians)))
        pygame.draw.lines(self.screen, color, False, points, px(3))

    # Arrowhead with a notched back: nose forward, two swept-back corners, a notch between them.
    def _draw_splash_ship(self, position, forward):
        side = (-forward[1], forward[0])

        def ship_point(local_x, local_y):
            return (position[0] + local_x * forward[0] + local_y * side[0],
                    position[1] + local_x * forward[1] + local_y * side[1])

        nose_len, half_width = px(22), px(13)
        points = [ship_point(nose_len, 0),
                  ship_point(-nose_len * 0.7, half_width),
                  ship_point(-nose_len * 0.35, 0),
                  ship_point(-nose_len * 0.7, -half_width)]
        pygame.draw.polygon(self.screen, theme.AMBER_BRIGHT, points)

    # ------------------------------------------------------------------
    # Cockpit panels: pilot ID, power, cloaking, nav-com, telemetry, controls
    # ------------------------------------------------------------------

    # The HUD once our own ship is gone: the same panels and readouts, in the error
    # state. Values read as dashes and the boxes are red. The only live controls are
    # watching another pilot and leaving.
    #
    # callsign: our own (lost) pilot name. watched: the pilot the camera is on.
    # number, total: which living pilot we're watching, out of how many.
    # options: [(action, label, key hint), ...] as for draw_options.
    def draw_spectate_hud(self, callsign, watched, number, total, options, show=True):
        if not show:
            return
        ERR = theme.RED
        ERR_DIM = theme.RED_DIM
        ERR_BRIGHT = theme.RED_BRIGHT
        blink_on = (pygame.time.get_ticks() // 400) % 2 == 0
        pad = px(22)
        small = ui_font(17)
        self.draw_ui_layout()

        # Pilot ID: our callsign, with the link down
        rect = self._callsign_rect()
        self._frame(rect, ERR)
        self._box_title(rect, "PILOT ID // LOST", ERR)
        rule_y = self._draw_callsign_name(rect, callsign or "UNREGISTERED", ERR_BRIGHT, ERR_DIM)
        value_x = rect.left + pad + small.size("IFF ")[0] + px(14)
        y = rule_y + px(10)
        for label, value in (("IFF", "--- ---"), ("LINK", "SIGNAL LOST")):
            self.screen.blit(small.render(label, True, ERR_DIM), (rect.left + pad, y))
            self.screen.blit(small.render(value, True, ERR), (value_x, y))
            y += small.get_height() + px(4)

        # Signal relay: the pilot we are watching, with PREV / NEXT
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        top = self._get_panel_rects()[0]
        relay = pygame.Rect(rect.right + px(24), rect.top,
                            max(px(160), radar_x - px(24) - (rect.right + px(24))), rect.height)
        self._frame(relay, ERR)
        self._box_title(relay, "SIGNAL RELAY", ERR)
        self.screen.blit(small.render(f"WATCHING {number:02d} OF {total:02d}", True, ERR_DIM),
                         (relay.left + pad, relay.top + px(34)))
        self.screen.blit(ui_font(26).render(watched, True, theme.GREEN),
                         (relay.left + pad, relay.top + px(34) + small.get_height() + px(4)))
        bh = px(34)
        bw = (relay.width - 2 * pad - px(10)) // 2
        by = relay.bottom - px(16) - bh
        self._button((relay.left + pad, by, bw, bh), "< PREV", 'spectate_prev', enabled=total > 1)
        self._button((relay.left + pad + bw + px(10), by, bw, bh), "NEXT >", 'spectate_next', enabled=total > 1)

        # Power: where the fuel and draw readouts would be
        power = pygame.Rect(radar_x, top.top + px(22), radar_size, top.height - px(44))
        self._frame(power, ERR)
        self._box_title(power, "POWER // NO FEED", ERR)
        readout = ui_font(26)
        y = power.top + px(34)
        self.screen.blit(readout.render("FUEL", True, ERR_DIM), (power.left + pad, y))
        self.screen.blit(readout.render(f"|{'-' * 6}|", True, ERR), (power.left + pad + px(110), y))
        y += readout.get_height() + px(6)
        self.screen.blit(readout.render("DRAW", True, ERR_DIM), (power.left + pad, y))
        dash = readout.render("----", True, ERR)
        self.screen.blit(dash, dash.get_rect(topright=(power.right - pad, y)))
        alert = ui_font(20).render("CARRIER LOST", True, ERR)
        if blink_on:
            box = pygame.Rect(0, 0, alert.get_width() + px(24), alert.get_height() + px(12))
            box.midbottom = (power.centerx, power.bottom - px(14))
            self._frame(box, ERR, tick=8, width=2)
            self.screen.blit(alert, alert.get_rect(center=box.center))

        # Radar: no returns
        radar = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        self._frame(radar, ERR, tick=12)
        self._box_title(radar, "RADAR // NO RETURNS", ERR)
        if blink_on:
            msg = ui_font(34).render("NO SIGNAL", True, ERR)
            self.screen.blit(msg, msg.get_rect(center=radar.center))

        # Telemetry: the same three columns as ship info, all dashes
        font = ui_font(19)
        line_h = font.get_height() + px(3)
        columns = [
            [("NAV-COM", ERR_DIM), ("POS  X ------  Y ------", ERR), ("GRID --", ERR),
             ("VEL  X ----  Y ----", ERR), (f"SPD  --- / {SHIP_MAX_SPEED:03d} U", ERR), ("HDG  --- DEG", ERR)],
            [("SUBSYSTEMS", ERR_DIM), ("INERT DAMP  [--]", ERR), ("BRAKE       [--]", ERR), ("LINK DOWN", ERR)],
            [("TACTICAL", ERR_DIM), ("THREAT  NO DATA", ERR), ("MSL  --/--  NO FEED", ERR), ("HULL  000/100", ERR)],
        ]
        rendered = [[font.render(t, True, c) for t, c in col] for col in columns]
        col_w = [max(s.get_width() for s in col) for col in rendered]
        gap = px(44)
        box_w = sum(col_w) + gap * (len(columns) - 1) + 2 * pad
        box_h = px(ui.THIN_HEIGHT - 24)
        _, _, _, world_bottom = self._get_world_bounds()
        tele = pygame.Rect(px(24), world_bottom + px(12), box_w, box_h)
        self._frame(tele, ERR)
        rows = max(len(c) for c in columns)
        y0 = tele.top + (box_h - rows * line_h) // 2 + px(4)
        x = tele.left + pad
        for col, cw in zip(rendered, col_w):
            for i, surf in enumerate(col):
                self.screen.blit(surf, (x, y0 + i * line_h))
            pygame.draw.line(self.screen, ERR_DIM, (x, y0 + line_h - px(2)), (x + cw, y0 + line_h - px(2)), px(1))
            x += cw + gap

        # Controls: the only live buttons left (watch, return)
        bank_left = tele.right + px(48)
        bank_w = self.screen.get_width() - px(24) - bank_left
        if bank_w >= px(150) and options:
            bank = pygame.Rect(bank_left, tele.top, bank_w, tele.height)
            self._frame(bank, ERR, tick=8)
            self._box_title(bank, "CONTROLS // OFFLINE", ERR, steady=True)
            inner = pygame.Rect(bank.left + px(14), bank.top + px(24), bank.width - px(28), bank.height - px(38))
            n, bgap = len(options), px(8)
            bw = min(px(360), (inner.width - bgap * (n - 1)) // n)
            bh = min(px(52), inner.height)
            by = inner.centery - bh // 2
            for i, (action, label, key_hint) in enumerate(options):
                self._button((inner.left + i * (bw + bgap), by, bw, bh), label, action, key=key_hint)

    # Switch banks in the left column, two buttons per row: helm and weapons on top,
    # sensors and displays beneath. The cloaking, deep field scan, laser and material
    # assessor keep their buttons on their own panels.
    def draw_control_banks(self, ship, missile_target, blink_busy=False,
                           vectors_on=True, sensor_buttons=(), hidden_buttons=(), show=True):
        if not show:
            return
        has_target = getattr(missile_target, 'net_id', None) is not None
        can_fire = ship.can_fire_missile() and has_target
        helm = [
            (f"FIRE MSL {ship.total_missiles:02d}", 'fire_missile',
             dict(key="P", lit=missile_target is not None, enabled=can_fire, lit_color=theme.AMBER_BRIGHT,
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
        gap = px(12)
        helm_h = (left.height - gap) // 2
        self._bank(pygame.Rect(left.left, left.top, left.width, helm_h), "HELM // WEAPONS", helm, 2)
        self._bank(pygame.Rect(left.left, left.top + helm_h + gap, left.width, left.height - helm_h - gap),
                   "SENSORS // DISPLAYS", displays, 2)

    # A framed bank of buttons in a grid. specs: (label, action, kwargs) per button.
    def _bank(self, rect, title, specs, cols):
        rect = pygame.Rect(rect)
        self._frame(rect, theme.AMBER_DIM, tick=8)
        self._box_title(rect, title, steady=True)
        if not specs:
            return

        pad, gap = px(14), px(8)
        head = px(24)
        rows = (len(specs) + cols - 1) // cols
        inner = pygame.Rect(rect.left + pad, rect.top + head, rect.width - 2 * pad, rect.height - head - pad)
        bw = (inner.width - gap * (cols - 1)) // cols
        bh = min(px(92), (inner.height - gap * (rows - 1)) // rows)
        top = inner.top + (inner.height - (bh * rows + gap * (rows - 1))) // 2
        big, small, key_font = ui_font(21), ui_font(14), ui_font(14)
        for i, (label, action, kwargs) in enumerate(specs):
            r, c = divmod(i, cols)
            style = dict(font=big, sub_font=small, key_font=key_font, **kwargs)
            self._button((inner.left + c * (bw + gap), top + r * (bh + gap), bw, bh), label, action, **style)

    # Fuel and current draw, in the top panel, framed to the width of the radar.
    def draw_power_readout(self, ship, show=True):
        if not show:
            return
        top = self._get_panel_rects()[0]
        font = ui_font(26)
        line_h = font.get_height() + px(6)

        radar_x, _, radar_size = self._get_radar_bounds()
        pad, gap, ack_w = px(16), px(16), px(170)
        alert_font = ui_font(20)
        box_h = 2 * line_h + px(14) + alert_font.get_height() + px(20 + 12)  # frame: 12 above the block, to the alert row's bottom
        y = top.centery - box_h // 2 + px(12)  # so the frame is centred in the top panel
        alert_y = y + 2 * line_h + px(14)
        panel_box = pygame.Rect(radar_x, y - px(12), radar_size, box_h)
        self._frame(panel_box, fill=theme.BG, tick=10, width=1)

        # Top rows: [fault button] then label / bar / value columns filling the rest
        x_val = panel_box.right - pad
        val_w = font.size("0000")[0]
        lab_w = font.size("DRAW")[0]
        x_lab = panel_box.left + pad + ack_w + gap
        x_bar = x_lab + lab_w + gap
        bar_w = x_val - val_w - gap - x_bar
        bar_cells = max(4, (bar_w - font.size("||")[0]) // font.size("#")[0])  # as many cells as fit

        fuel = max(0, min(SHIP_MAX_FUEL, ship.fuel))
        filled = round(bar_cells * fuel / SHIP_MAX_FUEL)
        frac = fuel / SHIP_MAX_FUEL
        bar_col = theme.RED if frac < 0.2 else (theme.AMBER_BRIGHT if frac < 0.4 else theme.GREEN)
        bar = font.render(f"|{'#' * filled}{' ' * (bar_cells - filled)}|", True, bar_col)

        self.screen.blit(font.render("FUEL", True, theme.AMBER_DIM), (x_lab, y))
        self.screen.blit(bar, (x_bar, y))
        self._fuel_bar_rect = pygame.Rect(x_bar, y, bar.get_width(), bar.get_height())
        self._throttle_rect = pygame.Rect(x_bar, y + line_h, bar.get_width(), font.get_height())
        fuel_val = font.render(f"{int(fuel):04d}", True, bar_col)
        self.screen.blit(fuel_val, fuel_val.get_rect(topright=(x_val, y)))

        self.screen.blit(font.render("DRAW", True, theme.AMBER_DIM), (x_lab, y + line_h))
        draw_val = font.render(f"{ship.current_draw:.2f}", True, theme.GREEN)
        self.screen.blit(draw_val, draw_val.get_rect(topright=(x_val, y + line_h)))

        # Fault acknowledge: left of the readout, as tall as its two rows
        self._button(pygame.Rect(panel_box.left + pad, y, ack_w, 2 * line_h),
                     "FAULT ACK", 'fuel_acknowledge', lit=ship.fuel_acknowledge)

        if ship.fuel_acknowledge:
            return

        # Alerts sit on a row under the readout. Each has a fixed slot so it never moves:
        # LOW FUEL bottom-left, HIGH DRAW bottom-right. The box only shows while its alert
        # is on, and the words flash inside it.
        low_fuel = SHIP_MAX_FUEL * LOW_FUEL_FRACTION
        blink_on = (pygame.time.get_ticks() // 300) % 2 == 0
        slots = [
            (fuel <= low_fuel, "LOW FUEL!", "left"),
            (ship.current_draw >= HIGH_USE, "WARNING, HIGH DRAW!", "right"),
        ]
        for active, text, side in slots:
            if not active:
                continue
            surf = alert_font.render(text, True, theme.RED)
            box = pygame.Rect(0, 0, surf.get_width() + px(24), surf.get_height() + px(12))
            if side == "left":
                box.topleft = (panel_box.left + pad, alert_y)
            else:
                box.topright = (panel_box.right - pad, alert_y)
            self._frame(box, theme.RED, fill=theme.BG, tick=8, width=2)
            if blink_on:
                self.screen.blit(surf, surf.get_rect(center=box.center))

    # Pilot ID readout: callsign, IFF code and link status.
    def draw_callsign_plate(self, callsign, player_id, pilots_on_net, local, show=True):
        if not show:
            return
        rect = self._callsign_rect()
        LABEL = theme.AMBER_DIM
        LIVE = theme.GREEN

        self._frame(rect)
        self._box_title(rect, "PILOT ID")

        pad = px(22)
        x = rect.left + pad
        name = callsign or "UNREGISTERED"
        rule_y = self._draw_callsign_name(rect, name, theme.AMBER_BRIGHT, theme.AMBER_FAINT)

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
        small = ui_font(17)
        line_h = small.get_height() + px(4)
        value_x = x + small.size("IFF ")[0] + px(14)
        y = rule_y + px(10)
        for label, value, color in rows:
            self.screen.blit(small.render(label, True, LABEL), (x, y))
            self.screen.blit(small.render(value, True, color), (value_x, y))
            y += line_h

        # Slot number at the end of the IFF row, and a carrier lamp at the end of the NET row
        slot = small.render(f"SLOT {player_id:02d}", True, LABEL)
        self.screen.blit(slot, slot.get_rect(topright=(rect.right - pad, rule_y + px(10))))
        if not local:
            lamp_on = (pygame.time.get_ticks() // 700) % 2 == 0
            lamp = (rect.right - pad - px(4), rule_y + px(10) + line_h + small.get_height() // 2)
            pygame.draw.circle(self.screen, LIVE if lamp_on else theme.GREEN_FAINT, lamp, px(4))

    # Cloaking readout in the bottom console: how visible the ship is to others, as a
    # percentage (100 = fully visible, 0 = hidden), plus five cells filled up to the cloaking
    # level, with the CLOAK -/+ buttons either side. Reads the true ship.visibility, so 0%
    # means enemies cannot see you.
    def draw_cloaking_level(self, ship, show=True):
        if not show:
            return
        level = max(0, min(5, int(ship.cloaking_value)))
        visible_percent = round(map_to_range_linear(ship.visibility, 0, 255, 0, 100))
        rect = self._cloak_rect()
        self._frame(rect)
        self._box_title(rect, "CLOAKING")

        value = ui_font(15).render(f"VISIBILITY: {visible_percent}%", True,
                                      theme.GREEN if visible_percent else theme.AMBER_DIM)
        self.screen.blit(value, value.get_rect(topright=(rect.right - px(22), rect.top + px(6))))

        # One row: DECLOAK | five level cells | CLOAK. The buttons register their own clicks.
        pad, gap = px(22), px(12)
        btn_w = btn_h = px(48)  # square
        row_top = rect.centery - btn_h // 2 + px(12)
        self._button(pygame.Rect(rect.left + pad, row_top, btn_w, btn_h), "-", "cloak_down",
                     enabled=level > 0, font=ui_font(26))
        self._button(pygame.Rect(rect.right - pad - btn_w, row_top, btn_w, btn_h), "+", "cloak_up",
                     enabled=level < 5, font=ui_font(26))

        cells_left = rect.left + pad + btn_w + gap
        cells_right = rect.right - pad - btn_w - gap
        cell_gap = px(8)
        cell_w = (cells_right - cells_left - 4 * cell_gap) // 5
        cell_h = px(22)
        y = row_top + (btn_h - cell_h) // 2
        for i in range(5):
            cell = pygame.Rect(cells_left + i * (cell_w + cell_gap), y, cell_w, cell_h)
            if i < level:
                pygame.draw.rect(self.screen, theme.GREEN, cell)
            else:
                pygame.draw.rect(self.screen, theme.AMBER_DIM, cell, px(2))

    # Navigation readout: in the bottom console, between the deep field scan and cloaking.
    def draw_navcom(self, ship, show=True):
        if not show:
            return
        rect = self._navcom_rect()
        self._frame(rect)
        self._box_title(rect, "NAV-COM")

        font = ui_font(20)
        line_h = font.get_height() + px(4)
        pad = px(22)
        rows = [
            ("POS", f"X {int(ship.pos_x):+06d}   Y {int(ship.pos_y):+06d}"),
            ("GRID", self.grid_ref(ship.pos_x, ship.pos_y)),
            ("VEL", f"X {ship.dir_x:+05.1f}   Y {ship.dir_y:+05.1f}"),
            ("SPD", f"{ship.speed:03.0f} / {SHIP_MAX_SPEED:03d} U"),
            ("HDG", f"{int(ship.heading) % 360:03d} DEG"),
        ]
        label_w = max(font.size(label)[0] for label, _ in rows) + px(24)
        top = rect.top + px(28) + max(0, (rect.height - px(36) - len(rows) * line_h) // 2)  # 28: below the title line
        for i, (label, value) in enumerate(rows):
            y = top + i * line_h
            self.screen.blit(font.render(label, True, theme.AMBER_DIM), (rect.left + pad, y))
            self.screen.blit(font.render(value, True, theme.GREEN), (rect.left + pad + label_w, y))

    # Ship telemetry: columns of readouts in the bottom panel, under the flight window.
    #
    # Column widths come from the text they hold, so nothing overlaps whatever the
    # numbers are; the box grows to fit and stays centred under the window.
    # dfs_warning: 'active' while a DFS sweep is on us, 'idle', or 'off' (alert muted).
    def draw_ship_info(self, ship, missile_target, enemy_has_missile_solution, instrument_lines=(),
                       dfs_warning='idle', show=True):
        if not show:
            return
        font = ui_font(19)
        line_h = font.get_height() + px(3)

        LIVE = theme.GREEN  # live readouts / system on
        CAUTION = theme.AMBER_BRIGHT
        THREAT = theme.RED
        LABEL = theme.AMBER_DIM  # headings and switched-off systems

        def on(flag):
            return LIVE if flag else LABEL

        # Column 1: subsystems (value in brackets drives the colour)
        subsystems = [
            ("SUBSYSTEMS", LABEL),
            (f"INERT DAMP  [{'ON' if ship.dampening else 'OFF'}]", on(ship.dampening)),
            (f"BRAKE       [{'ON' if ship.braking else 'OFF'}]", on(ship.braking)),
            *[(text, on(is_on)) for text, is_on in instrument_lines],
        ]

        # Column 2: tactical
        if ship.missile_cooling_down:
            msl = (f"MSL  {ship.total_missiles:02d}/{TOTAL_MISSILES:02d}  RCHG {ship.missile_cooldown_timer:.1f}S", CAUTION)
        else:
            msl = (f"MSL  {ship.total_missiles:02d}/{TOTAL_MISSILES:02d}  READY", LIVE)
        health = int(ship.health)
        hull_col = THREAT if health < 20 else (CAUTION if health < 40 else LIVE)
        if ship.painted or enemy_has_missile_solution:
            threat = ("THREAT  LOCK ON YOU" if enemy_has_missile_solution else "THREAT  RADAR PAINTED", THREAT)
        elif missile_target is not None:
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

        pad, gap = px(22), px(44)
        box_w = sum(col_w) + gap * (len(columns) - 1) + pad * 2
        box_h = px(ui.THIN_HEIGHT - 24)
        _, _, _, world_bottom = self._get_world_bounds()
        box = pygame.Rect(px(24), world_bottom + px(12), box_w, box_h)  # left end of the bottom strip
        self._frame(box)

        rows = max(len(c) for c in columns)
        y0 = box.top + (box_h - rows * line_h) // 2 + px(4)
        x = box.left + pad
        for col, w in zip(rendered, col_w):
            for i, surf in enumerate(col):
                self.screen.blit(surf, (x, y0 + i * line_h))
            # Heading underline
            pygame.draw.line(self.screen, theme.AMBER_FAINT, (x, y0 + line_h - px(2)), (x + w, y0 + line_h - px(2)), px(1))
            x += w + gap

    # Overlay on the ship in the flight window: a heading vector (where the nose points)
    # and a velocity vector (where and how fast it is moving), each with a label.
    # The heading vector has a fixed length; the velocity vector grows with speed.
    def draw_ship_vectors(self, ship, camera_x, camera_y, show=True):
        if not show:
            return
        cx = ship.rect.center[0] - camera_x
        cy = ship.rect.center[1] - camera_y
        old_clip = self.screen.get_clip()
        self.screen.set_clip(self._viewport_rect())

        font = ui_font(16)
        start_gap = 44  # world pixels, like the ship sprite: start outside the ship sprite

        # Heading: where the nose points
        fx, fy = ship.facing()
        hdg_start = (cx + fx * start_gap, cy + fy * start_gap)
        hdg_end = (cx + fx * (start_gap + px(k.HEADING_LEN)), cy + fy * (start_gap + px(k.HEADING_LEN)))
        self._arrow(hdg_start, hdg_end, theme.AMBER_BRIGHT)
        label = font.render(f"HDG {int(ship.heading) % 360:03d}", True, theme.AMBER_BRIGHT)
        self.screen.blit(label, label.get_rect(midbottom=(hdg_end[0], hdg_end[1] - px(6))))

        # Velocity: where it is moving, length = speed
        if ship.speed > 1:
            ux, uy = ship.dir_x, ship.dir_y
            length = px(k.SPEED_LEN) * min(1.0, ship.speed / SHIP_MAX_SPEED)
            vel_start = (cx + ux * start_gap, cy + uy * start_gap)
            vel_end = (cx + ux * (start_gap + length), cy + uy * (start_gap + length))
            self._arrow(vel_start, vel_end, theme.GREEN_BRIGHT)
            label = font.render(f"SPD {ship.speed:03.0f} U", True, theme.GREEN_BRIGHT)
            self.screen.blit(label, label.get_rect(topleft=(vel_end[0] + px(8), vel_end[1] + px(8))))

        self.screen.set_clip(old_clip)

    # A line from start to end with an arrowhead at end.
    def _arrow(self, start, end, color, width=2, head=10):
        pygame.draw.line(self.screen, color, start, end, px(width))
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        head = px(head)
        base = (end[0] - ux * head, end[1] - uy * head)
        wing = (-uy * head * 0.5, ux * head * 0.5)
        pygame.draw.polygon(self.screen, color, [
            end,
            (base[0] + wing[0], base[1] + wing[1]),
            (base[0] - wing[0], base[1] - wing[1]),
        ])

    # The panel backgrounds and borders: grimy, worn chassis, baked once per screen size.
    def draw_ui_layout(self, show=True):
        if not show:
            return
        screen_width, screen_height = self.screen.get_size()
        panels = self._get_panel_rects()

        key = (screen_width, screen_height)
        if self._panel_cache_key != key:
            labels = ["PNL-A1  //  ACCESS 7C", "PNL-B4  //  NO STEP", "PNL-L2", "PNL-R2"]
            # Old burned-in readouts go in the bottom panel's empty wings either side
            # of ship telemetry (panel-local coords). Other panels are covered by instruments.
            ghost_w = px(ui.PANEL_WIDTH - 140)
            ghost_h = px(ui.THIN_HEIGHT - 44)
            ghosts = [
                (),
                ((px(24), px(22), ghost_w, ghost_h),
                 (screen_width - px(24) - ghost_w, px(22), ghost_w, ghost_h)),
                (),
                (),
            ]
            self._panel_cache = [
                build_panel(p.size, 1983 + i, labels[i], k.BORDER, ghosts[i])
                for i, p in enumerate(panels)
            ]
            self._panel_cache_key = key
        for panel, surf in zip(panels, self._panel_cache):
            self.screen.blit(surf, panel)

    # ------------------------------------------------------------------
    # Overlays on the flight window
    # ------------------------------------------------------------------

    # Coordinate grid overlay in world space. The labels are world coordinates.
    def draw_world_grid(self, camera_x, camera_y, show_grid=True, show=True):
        if not show or not show_grid:
            return

        screen_width, screen_height = self.screen.get_size()
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        start_x = int(camera_x / GRID_SIZE) * GRID_SIZE
        start_y = int(camera_y / GRID_SIZE) * GRID_SIZE

        x = start_x
        while x < camera_x + screen_width:
            screen_x = x - camera_x
            if world_left < screen_x < world_right:
                pygame.draw.line(self.screen, k.SCOPE_GRID, (screen_x, world_top), (screen_x, world_bottom), 1)
                label = ui_legacy_font(k.FONT_SIZE_GRID).render(str(int(x)), True, k.SCOPE_GRID_TEXT)
                self.screen.blit(label, (screen_x + px(5), world_top + px(5)))
            x += GRID_SIZE

        y = start_y
        while y < camera_y + screen_height:
            screen_y = y - camera_y
            if world_top < screen_y < world_bottom:
                pygame.draw.line(self.screen, k.SCOPE_GRID, (world_left, screen_y), (world_right, screen_y), 1)
                label = ui_legacy_font(k.FONT_SIZE_GRID).render(str(int(y)), True, k.SCOPE_GRID_TEXT)
                self.screen.blit(label, (world_left + px(5), screen_y + px(5)))
            y += GRID_SIZE

    # Red blinking border around the flight window while a missile has a lock on us.
    def draw_missile_lock_warning(self, locked, show=True):
        if not show or not locked:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        self.lock_blink_counter += 1
        if (self.lock_blink_counter // k.LOCK_BLINK_FREQUENCY) % 2 == 0:
            pygame.draw.rect(self.screen, theme.RED,
                             (world_left, world_top, world_right - world_left, world_bottom - world_top),
                             px(k.LOCK_BORDER_WIDTH))

    # Flashing warning text when the ship is laser painted by an enemy.
    def draw_laser_painted_warning(self, painted, show=True):
        if not show or not painted:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        self.lock_blink_counter += 1
        if (self.lock_blink_counter // k.LASER_PAINTED_BLINK_FREQUENCY) % 2 == 0:
            # Bottom-right corner, clear of the gun-solution banner up top
            warning_text = ui_legacy_font(k.FONT_SIZE_BODY).render("LASER LOCK DETECTED", True, theme.RED_BRIGHT)
            self.screen.blit(warning_text, (world_right - warning_text.get_width() - px(20),
                                            world_bottom - warning_text.get_height() - px(20)))

    # Subtle catastrophe alert: a pulsing red border, a faint vignette and corner Xs.
    def draw_catastrophe_warning(self, active, show=True):
        if not show or not active:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        self.lock_blink_counter += 1
        if (self.lock_blink_counter // k.CATASTROPHE_STROBE_FREQUENCY) % 2 == 0:
            vignette_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
            pygame.draw.rect(vignette_surface, (*theme.RED, 25), (0, 0, screen_width, screen_height))
            self.screen.blit(vignette_surface, (0, 0))

            x_color = theme.RED_BRIGHT
            x_size = px(30)
            thickness = px(2)

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

            pygame.draw.rect(self.screen, theme.RED_BRIGHT,
                             (world_left, world_top, world_right - world_left, world_bottom - world_top), px(2))

    # Flashing red box in the bottom-left of the flight window while hull is critical.
    def draw_low_health_warning(self, low_health, show=True):
        if not show or not low_health:
            return

        world_left, _, _, world_bottom = self._get_world_bounds()
        box_x = world_left + px(10)
        box_y = world_bottom - px(120)
        box_w = px(150)
        box_h = px(100)

        self.health_blink_counter += 1
        if (self.health_blink_counter // 10) % 2 == 0:  # on for 10 frames, off for 10
            color = theme.RED
            pygame.draw.rect(self.screen, color, (box_x, box_y, box_w, box_h), px(2))
            pygame.draw.line(self.screen, color, (box_x, box_y), (box_x + box_w, box_y + box_h), px(2))
            pygame.draw.line(self.screen, color, (box_x + box_w, box_y), (box_x, box_y + box_h), px(2))

            text = ui_font(15).render("HULL CRITICAL", True, color)
            text_x = box_x + (box_w - text.get_width()) // 2
            text_y = box_y + box_h - text.get_height() - px(6)
            self.screen.blit(text, (text_x, text_y))

    # Blinking yellow box with a warning while the ship's shrink value is above 0.
    def draw_radiation_warning(self, shrink, show=True):
        if not show or shrink <= 0:
            return

        world_left, world_right, world_top, _ = self._get_world_bounds()
        text = ui_font(15).render("RADIATION DETECTED", True, k.RADIATION_YELLOW)
        box = pygame.Rect(0, 0, text.get_width() + px(24), text.get_height() + px(14))
        box.midtop = ((world_left + world_right) // 2, world_top + px(12))

        self.radiation_blink_counter += 1
        if (self.radiation_blink_counter // k.RADIATION_BLINK_FREQUENCY) % 2 == 0:
            pygame.draw.rect(self.screen, k.RADIATION_YELLOW, box, px(2))
            self.screen.blit(text, text.get_rect(center=box.center))

    # A single orange line sweeping left to right across the flight window, with the
    # warning text, while pirates have a lock and are firing.
    def draw_corpo_miner_fire_warning(self, pirate_firing, show=True):
        if not show or not pirate_firing:
            return

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        viewport_width = world_right - world_left

        self.pirate_sweep_counter += 1

        # Sweep position (0.0 to 1.0, then repeat)
        sweep_progress = (self.pirate_sweep_counter * 0.02) % 1.0
        line_x = world_left + (sweep_progress * viewport_width)

        # Pulsing brightness
        pulse = 0.4 + 0.6 * abs(math.sin(self.pirate_sweep_counter * 0.05))
        brightness = int(255 * pulse)
        color = (brightness, brightness // 4, brightness // 5)
        pygame.draw.line(self.screen, color, (line_x, world_top), (line_x, world_bottom), px(2))

        # Text pulses between readable and bright, never as dim as the sweep line
        text_color = theme.RED if pulse < 0.7 else theme.RED_BRIGHT
        warning_text = ui_legacy_font(24).render("HOSTILE GUN SOLUTION DETECTED", True, text_color)
        text_rect = warning_text.get_rect(midtop=((world_left + world_right) // 2, world_top + px(18)))
        pygame.draw.rect(self.screen, theme.BLACK, text_rect.inflate(px(16), px(6)))
        self.screen.blit(warning_text, text_rect)

    # Random horizontal bands of light across the screen when the ship takes a hit.
    def draw_bullet_damage_glitch(self, ship_took_damage, show=True):
        if not show or not ship_took_damage:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        glitch = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        num_glitch_lines = random.randint(3, 8)
        for _ in range(num_glitch_lines):
            glitch_y = random.randint(0, screen_height)
            glitch_height = random.randint(px(2), px(8))
            glitch_width = random.randint(px(100), px(400))
            glitch_x = random.randint(0, screen_width - glitch_width)
            glitch_color = (255, 255, random.randint(100, 200), 120)
            pygame.draw.rect(glitch, glitch_color, (glitch_x, glitch_y, glitch_width, glitch_height))

        self.screen.blit(glitch, (0, 0))

    # Flashing red tag over the fuel bar, and a second one under it, while the tank is empty.
    def draw_out_of_fuel_warning(self, out_of_fuel, show=True):
        if not show or not out_of_fuel or self._fuel_bar_rect is None:
            return

        box = self._fuel_bar_rect.inflate(px(8), px(8))
        on = (pygame.time.get_ticks() // 350) % 2 == 0
        col = theme.RED_BRIGHT if on else theme.RED
        self._frame(box, col, fill=theme.BG, tick=10, width=2)

        title = ui_font(20).render("DEPLETED", True, col)
        self.screen.blit(title, title.get_rect(center=box.center))

        # Systems throttled: a second tag in the free space under the bar, the largest size that fits
        if self._throttle_rect is not None:
            tag = self._throttle_rect.inflate(px(8), px(4))
            size = 18
            while size > 10 and ui_font(size).size("SYSTEMS THROTTLED")[0] > tag.width - px(8):
                size -= 1
            self._frame(tag, col, fill=theme.BG, tick=10, width=2)
            sub = ui_font(size).render("SYSTEMS THROTTLED", True, col)
            self.screen.blit(sub, sub.get_rect(center=tag.center))

    # Large text centred at the top of the flight window, on a dark plate. Call it every
    # frame the message should show. Starts a little lower than the gun-solution banner.
    def draw_viewport_banner(self, text, color=None, show=True):
        if not show or not text:
            return
        world_left, world_right, world_top, _ = self._get_world_bounds()
        banner_font = ui_font(44)
        line_color = color or theme.GREEN_BRIGHT
        max_width = (world_right - world_left) - px(120)
        lines = self._wrap_banner_text(text, banner_font, max_width)
        line_surfs = [banner_font.render(line, True, line_color) for line in lines]
        line_height = banner_font.get_linesize()
        block_width = max(surf.get_width() for surf in line_surfs)
        block_height = line_height * len(line_surfs)
        center_x = (world_left + world_right) // 2
        block_top = world_top + px(60)
        plate = pygame.Rect(0, 0, block_width, block_height).inflate(px(40), px(16))
        plate.midtop = (center_x, block_top - px(8))
        pygame.draw.rect(self.screen, theme.BLACK, plate)
        pygame.draw.rect(self.screen, line_color, plate, px(2))
        for index, surf in enumerate(line_surfs):
            self.screen.blit(surf, surf.get_rect(midtop=(center_x, block_top + index * line_height)))

    # Split `text` into lines no wider than `max_width` pixels, breaking on spaces.
    # A single word wider than max_width gets its own line, unbroken.
    def _wrap_banner_text(self, text, banner_font, max_width):
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

    # Pulsing scan sweep when being swept by DFS: a corner indicator and a red status box.
    def draw_dfs_warning(self, active, on, timer=0.0, show=True):
        if not show or not active or not on:
            return

        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        # Corner warning indicator (top right; the top left one is gone)
        pygame.draw.circle(self.screen, theme.RED, (world_right - px(15), world_top + px(15)), px(8), px(2))

        # Plain text in a red box, fixed at the top-left of the flight window
        warning_text = ui_legacy_font(28).render("STATUS: DFS SWEEP DETECTED", True, theme.RED)
        pad = px(10)
        box = pygame.Rect(world_left + px(32), world_top + px(30),
                          warning_text.get_width() + pad * 2, warning_text.get_height() + pad * 2)
        pygame.draw.rect(self.screen, theme.BG, box)
        pygame.draw.rect(self.screen, theme.RED, box, px(2))
        self.screen.blit(warning_text, (box.left + pad, box.top + pad))

    # Banner at the top of the flight window confirming a missile reached its contact.
    # Hard flicker as the hit registers, steady, then it stutters out over the last third.
    def draw_missile_contact(self, time_left, duration=1.5, show=True):
        if not show or time_left <= 0:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        elapsed = duration - time_left
        if elapsed < 0.25 and int(elapsed * 30) % 2:
            return
        if time_left < duration / 3 and int(time_left * 12) % 2:
            return

        text = ui_legacy_font(k.FONT_SIZE_SCAN_HEADER).render("MSL STATUS: CONTACT CONFIRMED", True, theme.AMBER_BRIGHT)
        pad_x, pad_y = px(18), px(8)
        box = pygame.Rect(0, 0, text.get_width() + pad_x * 2, text.get_height() + pad_y * 2)
        box.topleft = (world_left + px(16), world_top + px(64))
        self._frame(box, theme.AMBER, fill=theme.BG, tick=6)
        self.screen.blit(text, (box.left + pad_x, box.top + pad_y))

    # Banner across the top of the flight window when another pilot's ship goes down.
    # Flickers in and out, like the missile contact banner.
    def draw_ship_destroyed(self, time_left, duration, callsign, show=True):
        if not show or time_left <= 0:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        elapsed = duration - time_left
        if elapsed < 0.2 and int(elapsed * 30) % 2:
            return
        if time_left < duration / 4 and int(time_left * 12) % 2:
            return

        text = ui_legacy_font(k.FONT_SIZE_SCAN_HEADER).render(f"SHIP DESTRUCTION DETECTED: {callsign}", True, theme.RED)
        pad_x, pad_y = px(18), px(8)
        box = pygame.Rect(0, 0, text.get_width() + pad_x * 2, text.get_height() + pad_y * 2)
        box.midtop = ((world_left + world_right) // 2, world_top + px(16))
        self._frame(box, theme.RED, fill=theme.BG, tick=6)
        self.screen.blit(text, (box.left + pad_x, box.top + pad_y))

    # ------------------------------------------------------------------
    # Radar and the instruments that draw on it
    # ------------------------------------------------------------------

    # `rings` is how many distance rings to draw (0 for none). `movers` is (x, y) of each
    # moving thing the close range scan sees: drawn as plain red dots, no heading.
    def draw_radar(self, player_ship, signatures, is_scanning=False, sweep_angle=None, rings=0, movers=(), show=True):
        if not show:
            return
        radar_rect, center_x, center_y, max_radius = self._radar_geometry()
        radar_x, radar_y, radar_size = radar_rect.x, radar_rect.y, radar_rect.width

        # CRT phosphor background and scanlines
        pygame.draw.rect(self.screen, theme.BG_SENSOR, radar_rect)
        for y in range(radar_y, radar_y + radar_size, px(4)):
            pygame.draw.line(self.screen, theme.GREEN_FAINT, (radar_x, y), (radar_x + radar_size, y), px(1))
        self._frame(radar_rect, k.HUD_AMBER, fill=None, tick=15)

        # Tactical grid. The hardware clip keeps edge blips and grid lines inside the scope.
        old_clip = self.screen.get_clip()
        self.screen.set_clip(radar_rect)

        grid_color = theme.GREEN_DIM
        pygame.draw.line(self.screen, grid_color, (radar_x, center_y), (radar_x + radar_size, center_y), px(1))
        pygame.draw.line(self.screen, grid_color, (center_x, radar_y), (center_x, radar_y + radar_size), px(1))

        if rings:
            ring_layer = pygame.Surface(radar_rect.size, pygame.SRCALPHA)
            for i in range(1, rings + 1):
                pygame.draw.circle(ring_layer, theme.RANGE_RING, (center_x - radar_x, center_y - radar_y),
                                   round(max_radius * i / rings), px(1))
            self.screen.blit(ring_layer, radar_rect.topleft)

        # Out-of-bounds caution hatching: red diagonal lines wherever the map ends
        scale = max_radius / ui.RADAR_SCALE
        player_x, player_y = player_ship.rect.center
        w_left = center_x + (0 - player_x) * scale
        w_right = center_x + (self.world_width - player_x) * scale
        w_top = center_y + (0 - player_y) * scale
        w_bottom = center_y + (self.world_height - player_y) * scale
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
            for d in range(-r.height, r.width, px(80)):
                pygame.draw.line(self.screen, k.CAUTION_RED,
                                 (r.left + d, r.bottom), (r.left + d + r.height, r.top), px(2))
        self.screen.set_clip(radar_rect)
        # Solid red boundary line at the world edge
        edge = pygame.Rect(int(w_left), int(w_top), int(w_right - w_left), int(w_bottom - w_top))
        pygame.draw.rect(self.screen, k.CAUTION_RED, edge, px(2))

        # Player position: a glowing cluster
        pygame.draw.circle(self.screen, theme.WHITE, (center_x, center_y), px(3))
        pygame.draw.rect(self.screen, theme.WHITE, (center_x - px(1), center_y - px(1), px(3), px(3)))

        # Sweep arm: only while a scan is running (R), pointing at the ray being cast
        if sweep_angle is not None:
            arm_end = (center_x + math.cos(sweep_angle) * max_radius, center_y + math.sin(sweep_angle) * max_radius)
            pygame.draw.line(self.screen, theme.GREEN_BRIGHT, (center_x, center_y), arm_end, px(1))

        # Plot signatures as blocky retro blips
        for sig_x, sig_y, color in signatures:
            radar_px = int(center_x + (sig_x - player_x) * scale)
            radar_py = int(center_y + (sig_y - player_y) * scale)
            pygame.draw.rect(self.screen, color, (radar_px - px(2), radar_py - px(2), px(4), px(4)))
            pygame.draw.rect(self.screen, tuple(min(255, c + 110) for c in color), (radar_px - px(1), radar_py - px(1), px(2), px(2)))

        # Moving contacts from the close range scan: a red dot where each one is now
        for mover_x, mover_y in movers:
            radar_px = int(center_x + (mover_x - player_x) * scale)
            radar_py = int(center_y + (mover_y - player_y) * scale)
            pygame.draw.circle(self.screen, theme.RED, (radar_px, radar_py), px(3))

        self.screen.set_clip(old_clip)

        # Blinking label while scanning, steady otherwise
        show_label = True
        if is_scanning:
            show_label = (pygame.time.get_ticks() // 500) % 2 == 0

        if show_label:
            label_text = "RADAR [ SCANNING... ]" if is_scanning else "RADAR"
            label_color = k.DATA if is_scanning else k.HUD_AMBER
            label = ui_legacy_font(k.FONT_SIZE_RADAR).render(label_text, True, label_color)
            label_bg = pygame.Rect(radar_x + px(12), radar_y + px(12),
                                   label.get_width() + px(16), label.get_height() + px(6))
            pygame.draw.rect(self.screen, theme.BLACK, label_bg)
            pygame.draw.rect(self.screen, label_color, label_bg, px(1))
            self.screen.blit(label, label.get_rect(center=label_bg.center))

    # SWEEP button in the scope's top-right corner. Drawn after the laser and DFS lines
    # so they don't cross it.
    def draw_radar_controls(self, is_scanning, show=True):
        if not show:
            return
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        sweep = pygame.Rect(0, 0, px(112), px(34))
        sweep.topright = (radar_x + radar_size - px(12), radar_y + px(12))
        self._button(sweep, "SWEEP", 'radar_sweep', key="R", lit=is_scanning)

    # Tint each distance band (1 = innermost, of `band_count`) in `hot` on the radar.
    # Drawn after draw_radar, over the grid; faint enough to leave the blips readable.
    def draw_range_bands(self, hot, band_count, show=True):
        if not show or not hot:
            return
        radar_rect, center_x, center_y, max_radius = self._radar_geometry()
        spacing = max_radius / band_count
        layer = self._band_layer
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

    # The laser beam, drawn in the flight window and as a line on the radar.
    def draw_laser(self, laser, laser_endpoint, camera_x, camera_y, active, show=True):
        if not show or not active:
            return
        viewport = self._viewport_rect()
        radar_rect, center_x, center_y, max_radius = self._radar_geometry()
        radar_scale = max_radius / ui.RADAR_SCALE

        origin_x, origin_y = laser.ship.rect.center
        end_x, end_y = laser_endpoint
        beam_color = k.LASER_PAINTED if laser.painted else k.LASER_ACTIVE

        # --- 1. Flight window beam ---
        self.screen.set_clip(viewport)

        screen_origin = (origin_x - camera_x, origin_y - camera_y)
        screen_end = (end_x - camera_x, end_y - camera_y)

        # Retro glowing laser effect: thick coloured base with a hot white core
        pygame.draw.line(self.screen, beam_color, screen_origin, screen_end, 3)
        pygame.draw.line(self.screen, theme.WHITE, screen_origin, screen_end, 1)

        # Emitter box at the beam's origin, rotated to the beam direction so it reads as the
        # machine the beam comes out of (drawn over the beam start)
        rad = math.radians(laser.direction)
        fx, fy = math.cos(rad), math.sin(rad)  # along the beam
        side_x, side_y = -fy, fx  # across the beam
        half_len, half_wid = 5, 4
        cx, cy = screen_origin
        emitter = [
            (cx + fx * half_len + side_x * half_wid, cy + fy * half_len + side_y * half_wid),
            (cx + fx * half_len - side_x * half_wid, cy + fy * half_len - side_y * half_wid),
            (cx - fx * half_len - side_x * half_wid, cy - fy * half_len - side_y * half_wid),
            (cx - fx * half_len + side_x * half_wid, cy - fy * half_len + side_y * half_wid),
        ]
        pygame.draw.polygon(self.screen, theme.BG, emitter)
        pygame.draw.polygon(self.screen, beam_color, emitter, 1)

        # Impact flare at the endpoint
        pygame.draw.circle(self.screen, theme.WHITE, screen_end, 2)
        pygame.draw.circle(self.screen, beam_color, screen_end, 4, 1)

        # Range readout beside the impact point while locked
        if laser.laser_locked:
            label = ui_legacy_font(k.FONT_SIZE_SCAN_BODY).render(f"RNG {laser.target_distance:.0f}", True, theme.AMBER_BRIGHT)
            label_rect = label.get_rect(midleft=(screen_end[0] + px(14), screen_end[1] - px(14)))
            label_rect.clamp_ip(viewport)
            pygame.draw.rect(self.screen, theme.BG, label_rect.inflate(px(6), px(2)))
            self.screen.blit(label, label_rect)

        self.screen.set_clip(None)

        # --- 2. Radar beam: a sharp thin line from the scope centre, with a square impact blip ---
        rel_x = end_x - origin_x
        rel_y = end_y - origin_y
        radar_end_x = int(center_x + rel_x * radar_scale)
        radar_end_y = int(center_y + rel_y * radar_scale)

        self.screen.set_clip(radar_rect)
        pygame.draw.line(self.screen, beam_color, (center_x, center_y), (radar_end_x, radar_end_y), px(1))
        pygame.draw.rect(self.screen, theme.WHITE, (radar_end_x - px(1), radar_end_y - px(1), px(2), px(2)))
        self.screen.set_clip(None)

    # Mining beam from the ship to the rock it is burning: a layered beam with a pulsing
    # impact ring on the rock. The rock's material and percentage sit beside it.
    def draw_mining_beam(self, ship, rock, progress, camera_x, camera_y, show=True):
        if not show:
            return
        viewport = self._viewport_rect()
        self.screen.set_clip(viewport)

        sx = int(ship.center[0] - camera_x)
        sy = int(ship.center[1] - camera_y)
        ex = int(rock.pos_x - camera_x)
        ey = int(rock.pos_y - camera_y)

        # Same three layers as the laser: glow, inner, hot core
        pygame.draw.line(self.screen, theme.RED_DIM, (sx, sy), (ex, ey), 8)
        pygame.draw.line(self.screen, theme.RED_BRIGHT, (sx, sy), (ex, ey), 4)
        pygame.draw.line(self.screen, theme.WHITE, (sx, sy), (ex, ey), 2)

        # Impact ring and crosshair, pulsing
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

        label = ui_legacy_font(k.FONT_SIZE_SCAN_BODY).render(f"{rock.material.upper()} {progress * 100:.0f}%", True, theme.RED_BRIGHT)
        label_rect = label.get_rect(midleft=(ex + rock.size + px(8), ey))
        label_rect.clamp_ip(viewport)
        pygame.draw.rect(self.screen, theme.BG, label_rect.inflate(px(6), px(2)))
        self.screen.blit(label, label_rect)

        self.screen.set_clip(None)

    # The laser assessor box under the radar: what the beam is on, and the sweep, lock
    # and power buttons. target_type: the assessor's classification ("NOTHING" when clear).
    def draw_laser_targeting_info(self, target_type: str, laser_assessor, enabled: bool, show=True):
        if not show:
            return
        box = self._laser_box_rect()
        border_color = k.HUD_AMBER if enabled else theme.AMBER_DIM
        self._frame(box, border_color, tick=8)
        tab = self._border_tab(box, "LASER TARGET ANALYSIS", border_color)

        # Box split in half: status on top, buttons below
        top_h = box.height // 2

        # The assessor reports "NOTHING"; the scene starts out with "Nothing"
        has_contact = target_type.upper() != "NOTHING"
        locked = laser_assessor.laser_locked

        # Buttons fill the bottom half of the box, edge to edge inside the frame
        controls = pygame.Rect(box.left + px(8), box.top + top_h + px(4), box.width - px(16), box.height - top_h - px(8))
        self._button_row(controls, [
            (1, "<", 'arrow_key_left', dict(key="", enabled=enabled, hold=True, align="center")),
            (1, ">", 'arrow_key_right', dict(key="", enabled=enabled, hold=True, align="center")),
            (2, "LOCK", 'laser_lock', dict(key="SPC", lit=locked, enabled=enabled and (locked or has_contact),
                                           lit_color=theme.AMBER_BRIGHT)),
            (2, "PWR", 'toggle_laser', dict(key="I", lit=enabled)),
        ], gap=6)

        # Status readouts: one row in the top half, as large as fits there
        if enabled:
            text1 = f"CLASS: {target_type.upper()}"
            color1 = k.DATA if has_contact else theme.GREY
            if target_type.upper() == "ENEMY SHIP":
                blink_on = (pygame.time.get_ticks() // 350) % 2 == 0
                color1 = theme.RED_BRIGHT if blink_on else theme.RED_DIM
            if locked:
                text2, color2 = "STATUS: LOCK ACQUIRED", theme.AMBER_BRIGHT
            elif has_contact:
                text2, color2 = "STATUS: TRACKING", k.HUD_AMBER
            else:
                text2, color2 = "STATUS: SEARCHING", theme.GREY
        else:
            text1, color1 = "TARGETING INACTIVE", theme.GREY  # switched off is not a threat
            text2, color2 = "SYSTEM OFFLINE", theme.GREY

        region_top = box.top + tab.height // 2 + px(2)
        region = pygame.Rect(box.left + px(8), region_top, box.width - px(16), box.top + top_h - px(4) - region_top)
        surf1, surf2 = self._fit_status(region, [(text1, color1), (text2, color2)], gap=px(28))
        y = region.centery - surf1.get_height() // 2
        self.screen.blit(surf1, (region.left + px(8), y))
        self.screen.blit(surf2, (region.left + px(8) + surf1.get_width() + px(28), y))

    # Material assessor box: what the beam is on, scan progress, and the last result.
    #
    # assessor: MaterialAssessor (reads .laser, .scanning, .scan_progress(), .result)
    def draw_material_assessment(self, assessor, show=True):
        if not show:
            return
        box = self.material_box_rect()
        laser_target = assessor.laser_target()
        enabled = assessor.laser.on
        scanning = assessor.scanning is not None

        border_color = k.HUD_AMBER if enabled else theme.AMBER_DIM
        self._frame(box, border_color, tick=8)
        tab = self._border_tab(box, "MATERIAL ASSESSMENT", border_color)

        top_h = box.height // 2

        # Status words, most specific first
        if not enabled:
            text, color = "ASSESSOR OFFLINE", theme.GREY
        elif scanning:
            text, color = "SCANNING TARGET", theme.AMBER_BRIGHT
        elif laser_target is None:
            text, color = "NO TARGET UNDER BEAM", theme.GREY
        elif assessor.result is not None and assessor.result[0] is laser_target:
            found = assessor.result[1].upper()
            # A bracketed result is an identification, not a material, so it gets no label
            if found.startswith("["):
                text, color = found, theme.RED_BRIGHT
            else:
                text, color = f"MATERIAL: {found}", k.DATA
        else:
            text, color = "READY: PRESS SCAN", k.HUD_AMBER

        region_top = box.top + tab.height // 2 + px(2)
        region = pygame.Rect(box.left + px(8), region_top, box.width - px(16), box.top + top_h - px(22) - region_top)
        surf, = self._fit_status(region, [(text, color)])
        self.screen.blit(surf, (region.left + px(8), region.centery - surf.get_height() // 2))

        # Progress bar along the bottom of the top half: |###########     |
        # The segment count comes from the box width, so the bar runs edge to edge
        bar_font = ui_legacy_font(k.FONT_SIZE_SCAN_BODY)
        cell_w = bar_font.size("#")[0]
        target_w = box.width - px(28)
        segments = max(1, (target_w - bar_font.size("||")[0]) // cell_w)
        filled = round(segments * assessor.scan_progress())
        bar_text = "|" + "#" * filled + " " * (segments - filled) + "|"
        bar_surf = bar_font.render(bar_text, True, k.HUD_AMBER if scanning else theme.AMBER_DIM)
        self.screen.blit(bar_surf, bar_surf.get_rect(midleft=(box.left + px(14), box.top + top_h - px(14))))

    # SCAN button in the bottom half of the material box. Drawn after the panel so it sits on top.
    def draw_material_scan_button(self, assessor, show=True):
        if not show:
            return
        box = self.material_box_rect()
        top_h = box.height // 2
        controls = pygame.Rect(box.left + px(8), box.top + top_h + px(4), box.width - px(16), box.height - top_h - px(8))
        can_scan = assessor.scanning is None and assessor.laser_target() is not None
        self._button_row(controls, [
            (1, "SCAN", 'material_scan', dict(key="N", enabled=can_scan)),
        ])

    # Deep field scan readout in the bottom console: status, the last reading, and the
    # bearing and scan controls.
    def draw_deep_field_panel(self, has_result, reported_range, direction_index, system_online=True, show=True):
        if not show:
            return
        rect = self._deep_field_rect()
        self._frame(rect, k.SCOPE_BORDER, fill=k.SCOPE_BG, width=2)

        direction, degrees = k.DFS_HEADINGS[direction_index % 8]
        self._border_tab(rect, f"DEEP FIELD SCAN // {direction} {degrees:03d}°", k.SCOPE_BORDER, fill=k.SCOPE_BG)

        x = rect.left + px(15)
        # Status and the last scan's reading
        y = rect.top + px(28)
        if not system_online:
            self.screen.blit(ui_legacy_font(k.FONT_SIZE_SCAN_BODY).render("STATUS: OFFLINE", True, k.SCOPE_OFFLINE), (x, y))
            reading, color = "NO SIGNAL", k.SCOPE_OFFLINE
        else:
            self.screen.blit(ui_legacy_font(k.FONT_SIZE_SCAN_BODY).render("STATUS: ONLINE", True, k.SCOPE_ONLINE), (x, y))
            if not has_result:
                reading, color = "AWAITING SCAN", k.SCOPE_OFFLINE
            elif reported_range is None:
                reading, color = "NO MOVEMENT", k.SCOPE_OFFLINE
            else:
                reading, color = f"ENEMY MOVEMENT ~{int(round(reported_range, -1))} U", k.SCOPE_THREAT
        self.screen.blit(ui_legacy_font(k.FONT_SIZE_SCAN_BODY).render(reading, True, color), (x, y + px(34)))

        controls = pygame.Rect(rect.left + px(15), rect.bottom - px(15 + 42), rect.width - px(30), px(42))
        self._button_row(controls, [
            (2, "< BRG", 'dfs_bearing_ccw', dict(key="DN", enabled=system_online)),
            (2, "BRG >", 'dfs_bearing_cw', dict(key="UP", enabled=system_online)),
            (3, "RUN SCAN", 'dfs_scan', dict(key="O", enabled=system_online)),
            (2, "PWR", 'toggle_dfs', dict(key="K", lit=system_online)),
        ])

    # Deep field scan sweep: an amber baseline perpendicular to the scan heading, centred
    # on the player, with chevron arrows on the flight window (cleared at centre), and
    # orange scan lines edge to edge on the radar.
    def draw_dfs_corridor(self, player_ship, dfs_direction_index, camera_x, camera_y, active=False, show=True):
        if not show or not active:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        radar_x, radar_y, radar_size = self._get_radar_bounds()

        direction_deg = k.DFS_HEADINGS[dfs_direction_index % 8][1]
        origin_x, origin_y = player_ship.rect.center

        # Direction vectors, and the perpendicular (rotated 90 degrees)
        rad = math.radians(direction_deg - 90)
        forward_x = math.cos(rad)
        forward_y = math.sin(rad)
        perp_x = -forward_y
        perp_y = forward_x

        # Long enough to run past the screen and radar edges in both directions
        line_extent = 20000
        start_x = origin_x - perp_x * line_extent
        start_y = origin_y - perp_y * line_extent
        end_x = origin_x + perp_x * line_extent
        end_y = origin_y + perp_y * line_extent

        amber_color = k.SCOPE_HEADER
        orange_color = k.SCOPE_ORANGE

        # Arrow from (cx,cy) pointing along the scan heading.
        def arrow(cx, cy, length, head, width, color, line_w):
            tx, ty = cx + forward_x * length, cy + forward_y * length
            pygame.draw.line(self.screen, color, (cx, cy), (tx, ty), line_w)
            bx, by = tx - forward_x * head, ty - forward_y * head
            pygame.draw.polygon(self.screen, color, [
                (tx, ty),
                (bx - perp_x * width, by - perp_y * width),
                (bx + perp_x * width, by + perp_y * width)])

        # --- 1. Flight window: indicator on the ship ---
        self.screen.set_clip(self._viewport_rect())

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

        # --- 2. Radar: baseline plus one clear heading arrow ---
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2
        radar_scale = radar_size / ui.RADAR_SCALE

        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        self.screen.set_clip(radar_rect)

        radar_start = (center_x + (start_x - origin_x) * radar_scale,
                       center_y + (start_y - origin_y) * radar_scale)
        radar_end = (center_x + (end_x - origin_x) * radar_scale,
                     center_y + (end_y - origin_y) * radar_scale)
        pygame.draw.line(self.screen, orange_color, radar_start, radar_end, px(1))

        # Large arrow from the ship to the radar edge, in the scan direction
        arrow(center_x, center_y, radar_size * 0.12, px(8), px(5), amber_color, px(2))

        self.screen.set_clip(None)

    # ------------------------------------------------------------------
    # Tactical map and after-action replay
    # ------------------------------------------------------------------

    # The full-screen tactical map, centred on the ship.
    # confirmed_contacts: [(x, y, type, (vx, vy), confidence), ...].
    # marker_mode: None, 'PICK' (choosing a shape) or a shape name (waiting for a click on the map).
    def draw_tactical_map(self, active, player_ship, confirmed_contacts, scan_active=False, scan_range=1000,
                          laser_active=False, laser_direction=0, laser_locked=False, locked_object=None,
                          markers=(), marker_mode=None, show=True):
        if not show or not active:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        map_rect = pygame.Rect(px(ui.PANEL_WIDTH), px(ui.THIN_HEIGHT),
                               screen_width - 2 * px(ui.PANEL_WIDTH), screen_height - 2 * px(ui.THIN_HEIGHT))

        pygame.draw.rect(self.screen, k.SCOPE_BG, map_rect)

        previous_clip = self.screen.get_clip()
        self.screen.set_clip(map_rect)

        map_center = map_rect.center
        max_display_range = k.TACTICAL_MAP_RANGE

        # Centre on the same position the cockpit POS readout shows, so the
        # player dot sits exactly on its labelled coordinate.
        player_x, player_y = player_ship.pos_x, player_ship.pos_y
        scale = min(map_rect.width, map_rect.height) / (max_display_range * 2)

        # World coords (relative to player) to map panel pixels.
        def world_to_screen(wx, wy):
            return map_center[0] + wx * scale, map_center[1] + wy * scale

        self._map_view = (map_center, scale, player_x, player_y)

        # Placing a marker: the whole map is the click target. Registered before
        # the other map buttons so they stay on top of it.
        if marker_mode in k.MARKER_SHAPES:
            self.buttons.register(map_rect, 'marker_place')

        # World grid, dimmed
        view_margin = max_display_range * 1.5
        min_x = max(0, int((player_x - view_margin) // GRID_SIZE) * GRID_SIZE)
        max_x = min(self.world_width, int((player_x + view_margin) // GRID_SIZE + 1) * GRID_SIZE)
        min_y = max(0, int((player_y - view_margin) // GRID_SIZE) * GRID_SIZE)
        max_y = min(self.world_height, int((player_y + view_margin) // GRID_SIZE + 1) * GRID_SIZE)

        for gx in range(min_x, max_x + 1, GRID_SIZE):
            p1 = world_to_screen(gx - player_x, min_y - player_y)
            p2 = world_to_screen(gx - player_x, max_y - player_y)
            pygame.draw.line(self.screen, theme.GREEN_FAINT, p1, p2, px(1))

        for gy in range(min_y, max_y + 1, GRID_SIZE):
            p1 = world_to_screen(min_x - player_x, gy - player_y)
            p2 = world_to_screen(max_x - player_x, gy - player_y)
            pygame.draw.line(self.screen, theme.GREEN_FAINT, p1, p2, px(1))

        # World boundaries
        boundary_pts = [
            world_to_screen(0 - player_x, 0 - player_y),
            world_to_screen(self.world_width - player_x, 0 - player_y),
            world_to_screen(self.world_width - player_x, self.world_height - player_y),
            world_to_screen(0 - player_x, self.world_height - player_y),
        ]
        pygame.draw.polygon(self.screen, theme.AMBER_DIM, boundary_pts, px(1))

        # Shrink: the quadrant the ship is in, once it has sat still long enough to shrink
        if player_ship.shrink > 0:
            x0, y0, x1, y1 = self.shrink_quadrant(player_x, player_y, player_ship.shrink)
            top_left = world_to_screen(x0 - player_x, y0 - player_y)
            bottom_right = world_to_screen(x1 - player_x, y1 - player_y)
            quadrant = pygame.Rect(int(top_left[0]), int(top_left[1]),
                                   int(bottom_right[0] - top_left[0]), int(bottom_right[1] - top_left[1]))
            highlight = pygame.Surface(quadrant.size, pygame.SRCALPHA)
            highlight.fill((*theme.AMBER_BRIGHT, 40))
            self.screen.blit(highlight, quadrant.topleft)
            pygame.draw.rect(self.screen, theme.AMBER_BRIGHT, quadrant, px(2))

        # Close-range scan radius
        if scan_active:
            radius_px = scan_range * scale
            pygame.draw.circle(self.screen, (*theme.GREEN_FAINT, 40), map_center, int(radius_px))
            pygame.draw.circle(self.screen, (*theme.GREEN_DIM, 100), map_center, int(radius_px), px(1))

        # Laser beam, amber while locked
        if laser_active:
            rad = math.radians(laser_direction - 90)
            beam_end = world_to_screen(math.cos(rad) * LASER_RANGE, math.sin(rad) * LASER_RANGE)
            beam_color = theme.AMBER_BRIGHT if laser_locked else theme.GREEN
            pygame.draw.line(self.screen, beam_color, world_to_screen(0, 0), beam_end, px(2))

            if laser_locked and locked_object:
                obj_x = getattr(locked_object, 'pos_x', None) or locked_object.rect.center[0]
                obj_y = getattr(locked_object, 'pos_y', None) or locked_object.rect.center[1]
                lock_screen = world_to_screen(obj_x - player_x, obj_y - player_y)
                pygame.draw.circle(self.screen, theme.AMBER_BRIGHT, lock_screen, px(12), px(2))

        # Confirmed contacts, fading with confidence
        for pos_x, pos_y, contact_type, velocity, confidence in confirmed_contacts:
            screen_x, screen_y = world_to_screen(pos_x - player_x, pos_y - player_y)

            # Size and colour scale with confidence
            marker_size = px(max(2, int(3 + confidence * 6)))
            alpha = int(255 * confidence)
            color = k.SCOPE_DATA
            kind = contact_type.lower()
            pos = (int(screen_x), int(screen_y))

            # Temporary surface, so the symbol alpha-blends
            marker_surface = pygame.Surface((marker_size * 3, marker_size * 3), pygame.SRCALPHA)
            marker_center = (marker_size + 1, marker_size + 1)

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
                pygame.draw.polygon(marker_surface, (*theme.GREEN_BRIGHT, alpha),
                                    [(marker_center[0] + marker_size, marker_center[1]),
                                     (marker_center[0] - marker_size // 2, marker_center[1] - marker_size),
                                     (marker_center[0] - marker_size // 2, marker_center[1] + marker_size)])
            else:
                pygame.draw.circle(marker_surface, (*color, alpha), marker_center, marker_size, px(1))

            self.screen.blit(marker_surface, (pos[0] - marker_center[0], pos[1] - marker_center[1]))

            # Velocity vector, fading with confidence
            vx, vy = velocity
            if (vx != 0 or vy != 0) and confidence > 0.1:
                vector_length = px(25)
                vel_mag = math.hypot(vx, vy)
                if vel_mag > 0:
                    dir_x = vx / vel_mag
                    dir_y = vy / vel_mag
                    head = (int(screen_x + dir_x * vector_length), int(screen_y + dir_y * vector_length))
                    pygame.draw.line(self.screen, (*color, alpha), pos, head, px(1))

        # Player markers (local only)
        for i, (shape, mx, my) in enumerate(markers, 1):
            mpos = world_to_screen(mx - player_x, my - player_y)
            self._draw_marker_shape(self.screen, shape, mpos, px(9), theme.AMBER_BRIGHT)
            tag = ui_legacy_font(k.FONT_SIZE_TINY).render(str(i), True, theme.AMBER_BRIGHT)
            self.screen.blit(tag, (mpos[0] + px(12), mpos[1] - tag.get_height() // 2))

        # Player centre
        pygame.draw.circle(self.screen, theme.WHITE, map_center, px(5))

        # Grid coordinates: cell indices pinned to the panel edges, so they stay readable as
        # the map scrolls, and kept clear of the header and close button
        label_top = map_rect.top + px(56)
        label_left = map_rect.left + px(8)
        for col in range(min_x // GRID_SIZE, max_x // GRID_SIZE):
            sx, _ = world_to_screen(col * GRID_SIZE + GRID_SIZE / 2 - player_x, 0)
            if map_rect.left + px(40) < sx < map_rect.right - px(10):
                txt = ui_legacy_font(k.FONT_SIZE_TINY).render(f"{col}X", True, k.SCOPE_GRID_TEXT)
                self.screen.blit(txt, txt.get_rect(midtop=(int(sx), label_top)))
        for row in range(min_y // GRID_SIZE, max_y // GRID_SIZE):
            _, sy = world_to_screen(0, row * GRID_SIZE + GRID_SIZE / 2 - player_y)
            if label_top + px(20) < sy < map_rect.bottom - px(40):
                txt = ui_legacy_font(k.FONT_SIZE_TINY).render(f"{row}Y", True, k.SCOPE_GRID_TEXT)
                self.screen.blit(txt, txt.get_rect(midleft=(label_left, int(sy))))

        self.screen.set_clip(previous_clip)
        # Frame last so contacts near the edge never draw over it
        self._frame(map_rect, k.SCOPE_BORDER, fill=None, width=2, tick=14)

        # Header and footer
        header = f"TACTICAL MAP  //  GRID {self.grid_ref(player_x, player_y)}"
        self.screen.blit(ui_legacy_font(k.FONT_SIZE_SCAN_HEADER).render(header, True, k.SCOPE_HEADER), (map_rect.x + px(18), map_rect.y + px(14)))

        contact_count = len(confirmed_contacts)
        moving_count = sum(1 for c in confirmed_contacts if c[3][0] != 0 or c[3][1] != 0)
        avg_confidence = (sum(c[4] for c in confirmed_contacts) / contact_count * 100) if contact_count > 0 else 0
        footer = f"CONFIRMED: {contact_count}  MOVING: {moving_count}  SIGNAL: {int(avg_confidence)}%"
        txt_footer = ui_legacy_font(k.FONT_SIZE_SCAN_BODY).render(footer, True, k.SCOPE_DATA)
        self.screen.blit(txt_footer, (map_rect.x + px(18), map_rect.bottom - txt_footer.get_height() - px(14)))

        close = pygame.Rect(0, 0, px(110), px(34))
        close.topright = (map_rect.right - px(14), map_rect.top + px(14))
        self._button(close, "CLOSE", 'toggle_map', key="M")

        # Marker controls, bottom right
        if marker_mode in k.MARKER_SHAPES:
            prompt = ui_legacy_font(k.FONT_SIZE_SCAN_BODY).render(f"CLICK THE MAP TO PLACE {marker_mode}", True, k.SCOPE_HEADER)
            self.screen.blit(prompt, prompt.get_rect(midbottom=(map_rect.centerx, map_rect.bottom - px(14))))
        if marker_mode == 'PICK':
            specs = [(1, shape, f'marker_shape_{shape.lower()}', {}) for shape in k.MARKER_SHAPES]
            specs.append((1, "CANCEL", 'marker_cancel', {}))
        elif marker_mode in k.MARKER_SHAPES:
            specs = [(1, "CANCEL", 'marker_cancel', {})]
        else:
            specs = [(2, "ADD MARKER", 'marker_add', {}),
                     (2, "CLEAR MARKERS", 'marker_clear', dict(enabled=bool(markers)))]
        n = len(specs)
        row = pygame.Rect(0, 0, px(130 * n + 8 * (n - 1) + (40 if marker_mode is None else 0)), px(34))
        row.bottomright = (map_rect.right - px(14), map_rect.bottom - px(14))
        self._button_row(row, specs)

    @staticmethod
    def _draw_marker_shape(surface, shape, center, size, color):
        cx, cy = int(center[0]), int(center[1])
        if shape == "CIRCLE":
            pygame.draw.circle(surface, color, (cx, cy), size, px(2))
        elif shape == "SQUARE":
            pygame.draw.rect(surface, color, (cx - size, cy - size, size * 2, size * 2), px(2))
        elif shape == "TRIANGLE":
            pygame.draw.polygon(surface, color, [(cx, cy - size), (cx - size, cy + size), (cx + size, cy + size)], px(2))
        elif shape == "DIAMOND":
            pygame.draw.polygon(surface, color, [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], px(2))
        else:  # CROSS
            pygame.draw.line(surface, color, (cx - size, cy), (cx + size, cy), px(2))
            pygame.draw.line(surface, color, (cx, cy - size), (cx, cy + size), px(2))

    # World position under a screen point on the tactical map (from the last drawn frame).
    def map_screen_to_world(self, pos):
        center, scale, player_x, player_y = self._map_view
        return (player_x + (pos[0] - center[0]) / scale,
                player_y + (pos[1] - center[1]) / scale)

    # (shape, world_x, world_y) for the latest map click, placed with marker_mode.
    # None when marker_mode is not a shape or no button-hit click has happened yet.
    def marker_from_click(self, marker_mode):
        click = self.buttons.last_click_pos
        if marker_mode not in k.MARKER_SHAPES or click is None:
            return None
        wx, wy = self.map_screen_to_world(click)
        return (marker_mode, wx, wy)

    # After-action replay: the whole world with every asteroid as a circle, and each
    # pilot's recorded flight drawn up to `progress` (in samples, see ReplayState).
    # pilots: [(callsign, [(x, y), ...]), ...]. The control buttons are registered here
    # with replay_* actions, which MainScene routes.
    def draw_replay_map(self, asteroids, pilots, world_width, world_height, progress, playing, last_sample, show=True):
        if not show:
            return
        w, h = self.screen.get_size()
        x0 = px(k.PLAIN_MARGIN)
        top = px(k.PLAIN_TOP)
        head = ui_font(k.MENU_SMALL_SIZE)
        body = ui_font(k.MENU_FONT_SIZE)

        self.screen.blit(head.render("ERGOT SYSTEMS // FLIGHT REPLAY", True, theme.AMBER_DIM), (x0, top))
        elapsed = int(progress * POSITION_RECORD_SECONDS)
        clock = head.render(f"T+ {elapsed // 60:02d}:{elapsed % 60:02d}", True, theme.AMBER_BRIGHT)
        self.screen.blit(clock, clock.get_rect(topright=(w - x0, top)))
        rule_y = top + head.get_height() + px(10)
        pygame.draw.line(self.screen, theme.AMBER_FAINT, (x0, rule_y), (w - x0, rule_y), px(1))

        # Legend: one line per pilot, in the colour of its path
        legend_w = px(260)
        y = rule_y + px(24)
        for i, (callsign, _) in enumerate(pilots):
            color = k.REPLAY_PILOT_COLORS[i % len(k.REPLAY_PILOT_COLORS)]
            mid = y + body.get_height() // 2
            pygame.draw.line(self.screen, color, (x0, mid), (x0 + px(24), mid), px(3))
            self.screen.blit(body.render(callsign.upper(), True, color), (x0 + px(36), y))
            y += body.get_height() + px(10)

        map_left = x0 + legend_w + px(24)
        map_rect = pygame.Rect(map_left, rule_y + px(24), w - map_left - x0, h - rule_y - px(24 + 110))
        pygame.draw.rect(self.screen, k.SCOPE_BG, map_rect)

        # The whole world fits the panel, centred, at one scale on both axes
        scale = min(map_rect.width / world_width, map_rect.height / world_height)
        origin_x = map_rect.left + (map_rect.width - world_width * scale) / 2
        origin_y = map_rect.top + (map_rect.height - world_height * scale) / 2

        def to_screen(wx, wy):
            return origin_x + wx * scale, origin_y + wy * scale

        previous_clip = self.screen.get_clip()
        self.screen.set_clip(map_rect)

        pygame.draw.rect(self.screen, theme.AMBER_DIM,
                         (int(origin_x), int(origin_y), int(world_width * scale), int(world_height * scale)), px(1))

        for asteroid in asteroids:
            centre = to_screen(asteroid.pos_x, asteroid.pos_y)
            pygame.draw.circle(self.screen, theme.ASTEROID, (int(centre[0]), int(centre[1])),
                               max(1, int(asteroid.size * scale)), px(1))

        for i, (_, path) in enumerate(pilots):
            color = k.REPLAY_PILOT_COLORS[i % len(k.REPLAY_PILOT_COLORS)]
            runs, gaps = self._track_runs(path, progress)
            for run in runs:
                points = [to_screen(x, y) for x, y in run]
                if len(points) >= 2:
                    pygame.draw.lines(self.screen, color, False, points, px(2))
            for before, after in gaps:
                self._draw_blink_mark(to_screen(*before), color)
                if after is not None:
                    self._draw_blink_mark(to_screen(*after), color)
                    self._draw_dashed_line(to_screen(*before), to_screen(*after), color)
            if runs and runs[-1]:
                head_x, head_y = to_screen(*runs[-1][-1])
                pygame.draw.circle(self.screen, color, (int(head_x), int(head_y)), px(4))

        self.screen.set_clip(previous_clip)
        self._frame(map_rect, k.SCOPE_BORDER, fill=None, width=2, tick=14)

        # Controls under the map. Each is greyed out when it would do nothing.
        specs = [
            (1, "BACK", 'replay_back', dict(key="LEFT", enabled=progress > 0)),
            (1, "PAUSE" if playing else "PLAY", 'replay_play', dict(key="SPACE", enabled=last_sample > 0)),
            (1, "STEP", 'replay_forward', dict(key="RIGHT", enabled=progress < last_sample)),
            (1, "EXIT REPLAY", 'replay_exit', dict(key="ESC")),
        ]
        self._button_row(pygame.Rect(map_rect.left, map_rect.bottom + px(20), map_rect.width, px(40)), specs)

    # A recorded path up to `progress` samples, as (runs, gaps).
    #
    # runs: lists of points to join with lines. A blink mark ends a run, so nothing is
    # drawn across it. The last point of the final run is interpolated between the two
    # samples the progress falls between.
    # gaps: one (before, after) pair per blink. before is the last point before the jump,
    # after the first point past it. after is None until the progress reaches it.
    @staticmethod
    def _track_runs(path, progress):
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
        size = px(size)
        pygame.draw.line(self.screen, color, (cx - size, cy - size), (cx + size, cy + size), px(2))
        pygame.draw.line(self.screen, color, (cx - size, cy + size), (cx + size, cy - size), px(2))

    def _draw_dashed_line(self, start, end, color, dash=6, gap=5):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if length == 0:
            return
        dx, dy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
        dash, gap = px(dash), px(gap)
        distance = 0.0
        while distance < length:
            seg_end = min(distance + dash, length)
            a = (start[0] + dx * distance, start[1] + dy * distance)
            b = (start[0] + dx * seg_end, start[1] + dy * seg_end)
            pygame.draw.line(self.screen, color, a, b, px(1))
            distance += dash + gap

    # ------------------------------------------------------------------
    # Map helpers used by the scene: world size, grid labels, hull feedback
    # ------------------------------------------------------------------

    # The world the scene is showing: its size is what the radar and map are drawn to.
    def set_world(self, world):
        self.world_width, self.world_height = world.width, world.height

    # Size of the screen the world is drawn to, in pixels.
    def view_size(self):
        return self.screen.get_size()

    # Grid cell containing a world position, as '<col>X <row>Y' (clamped to the world).
    def grid_ref(self, x, y):
        col = min(max(int(x // GRID_SIZE), 0), self.world_width // GRID_SIZE - 1)
        row = min(max(int(y // GRID_SIZE), 0), self.world_height // GRID_SIZE - 1)
        return f"{col}X {row}Y"

    # World rectangle (x0, y0, x1, y1) of the quadrant holding (pos_x, pos_y) after `level` halvings
    # of the world. Each level halves the current quadrant again; halving stops once a half
    # would be narrower or shorter than one grid cell, so that is the smallest quadrant.
    def shrink_quadrant(self, pos_x, pos_y, level):
        x0, y0, x1, y1 = 0, 0, self.world_width, self.world_height
        for _ in range(level):
            if (x1 - x0) / 2 < GRID_SIZE or (y1 - y0) / 2 < GRID_SIZE:
                break
            mid_x = (x0 + x1) / 2
            mid_y = (y0 + y1) / 2
            if pos_x < mid_x:
                x1 = mid_x
            else:
                x0 = mid_x
            if pos_y < mid_y:
                y1 = mid_y
            else:
                y0 = mid_y
        return x0, y0, x1, y1

    def impact_asteroid(self):
        crt.impact(*k.IMPACT_ASTEROID)

    def impact_missile(self):
        crt.impact(*k.IMPACT_MISSILE)

    # The picture's tearing follows the hull: clean at full health, worst at zero.
    def set_hull_damage(self, health):
        crt.set_damage(health)

    # The operator console over whatever the scene has drawn so far.
    def draw_pause_console(self, pause, show=True):
        if not show:
            return
        pause.draw(self.screen, self.buttons)
