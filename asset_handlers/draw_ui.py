import math
import random

import pygame
from utility.constants import *
from utility.ui_constants import COLOR_DFS_GRAY


class DrawUI:
    # region constant
    PANEL_WIDTH = 600
    THIN_HEIGHT = 200
    NOTCH_LENGTH = 12
    NOTCH_WIDTH = 3

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
    MISSILE_LOCK_BOX_SIZE = 12

    # Color Palette (CRT Amber/Cyan Theme)
    COLOR_PANEL_BG = (3, 8, 5)
    COLOR_BORDER_PRIMARY = (210, 150, 0)
    COLOR_BORDER_INSET = (90, 65, 0)
    COLOR_CORNER_ACCENT = (255, 200, 40)
    COLOR_HUD_CYAN = (0, 255, 200)
    COLOR_HUD_AMBER = (200, 150, 0)
    COLOR_GRID = (100, 100, 80)
    COLOR_GRID_TEXT = (150, 150, 100)
    COLOR_SCANLINE = (0, 0, 0)

    # DFS Colors
    COLOR_DFS_BG = (5, 12, 8)
    COLOR_DFS_BORDER = (210, 150, 0)
    COLOR_DFS_INSET = (90, 65, 0)
    COLOR_DFS_AMBER = (255, 200, 40)
    COLOR_DFS_GREEN = (80, 220, 130)
    COLOR_DFS_CYAN = (0, 220, 220)
    COLOR_DFS_WHITE = (220, 220, 180)
    COLOR_DFS_GRAY = (120, 120, 90)
    COLOR_DFS_RED = (220, 50, 50)
    COLOR_DFS_YELLOW = (220, 220, 50)

    # Laser/Targeting Colors
    COLOR_LASER_ACTIVE = (0, 255, 160)  # Cyan
    COLOR_LASER_PAINTED = (150, 30, 30)  # Red

    # Threat/Warning Colors
    COLOR_THREAT_RED = (255, 0, 0)
    COLOR_THREAT_DIM = (150, 50, 50)
    COLOR_MISSILE_VECTOR = (255, 140, 0)  # CRT Orange
    COLOR_MISSILE_LOCK = (255, 40, 40)

    # Corridor Display
    COLOR_CORRIDOR_BRIGHT = (0, 255, 200)
    COLOR_CORRIDOR_DIM = (0, 120, 90)
    COLOR_CORRIDOR_FILL = (0, 255, 180, 18)
    COLOR_CORRIDOR_RADAR = (0, 255, 180, 30)

    # Font Sizes
    FONT_SIZE_LARGE = 35
    FONT_SIZE_BODY = 28
    FONT_SIZE_RADAR = 25
    FONT_SIZE_SCAN_HEADER = 32
    FONT_SIZE_SCAN_BODY = 24
    FONT_SIZE_GRID = 14
    FONT_SIZE_TINY = 14

    # Scanline Configuration
    SCANLINE_HEIGHT = 1
    SCANLINE_SPACING = 4
    SCANLINE_ALPHA = 100

    # Blink Configuration
    LOCK_BLINK_FREQUENCY = 10
    LOCK_BORDER_WIDTH = 10

    # endregion

    def __init__(self, screen):
        self.screen = screen
        self.lock_blink_counter = 0

        # Initialize all fonts at once
        self.font_large = pygame.font.Font(None, self.FONT_SIZE_LARGE)
        self.font_body = pygame.font.Font(None, self.FONT_SIZE_BODY)
        self.font_radar_label = pygame.font.Font(None, self.FONT_SIZE_RADAR)
        self.font_scan_header = pygame.font.Font(None, self.FONT_SIZE_SCAN_HEADER)
        self.font_scan_body = pygame.font.Font(None, self.FONT_SIZE_SCAN_BODY)
        self.font_grid = pygame.font.Font(None, self.FONT_SIZE_GRID)
        self.font_tiny = pygame.font.Font(None, self.FONT_SIZE_TINY)

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
        radar_size = min(radar_size, self.PANEL_WIDTH - 2 * self.RADAR_PADDING)

        return radar_x, radar_y, radar_size

    def draw_ship_info(self, ship):
        """Draw framed retro CRT ship telemetry inside the bottom panel.

        Dynamically centers text vertically and scales layout for legibility.
        """
        screen_height = self.screen.get_height()

        # Anchor safely inside the bottom panel area
        panel_y_top = screen_height - self.THIN_HEIGHT
        panel_offset_x = getattr(self, "PANEL_WIDTH", 0) + 12

        # Container Box Dimensions
        box_x = panel_offset_x
        box_y = panel_y_top + 6
        box_w = 720
        box_h = self.THIN_HEIGHT - 12

        # UI Theme Colors
        COLOR_CYAN = getattr(self, "COLOR_HUD_CYAN", (0, 255, 255))
        COLOR_AMBER = getattr(self, "COLOR_HUD_YELLOW", (255, 180, 0))
        COLOR_RED = getattr(self, "COLOR_HUD_RED", (255, 60, 60))
        COLOR_BORDER = getattr(self, "COLOR_BORDER_INSET", (0, 150, 150))
        COLOR_BG = getattr(self, "COLOR_PANEL_BG", (10, 15, 20))
        COLOR_DIM = (0, 120, 120)

        # 1. UPGRADED FONT
        font = pygame.font.SysFont("monospace", 17, bold=True)

        # 2. VERTICAL CENTERING MATH (5 lines now for subsystems)
        line_h = font.get_height() + 2
        total_text_h = line_h * 5
        start_y = box_y + (box_h - total_text_h) // 2

        # 3. COLUMN POSITIONS
        col1_x = box_x + 16
        col2_x = box_x + 300
        col3_x = box_x + 500

        # --- DRAW BOUNDING BOX FRAME ---
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        pygame.draw.rect(self.screen, COLOR_BG, box_rect)
        pygame.draw.rect(self.screen, COLOR_BORDER, box_rect, 1)

        # Frame Header Badge
        hdr_text = font.render(" [ SHIP TELEMETRY ] ", True, COLOR_BORDER)
        self.screen.blit(hdr_text, (box_x + 14, (box_y + 20) - (hdr_text.get_height() - 20 // 2)))

        # Corner Accent Ticks
        tick_len = 6
        pygame.draw.line(self.screen, COLOR_CYAN, (box_x, box_y), (box_x + tick_len, box_y), 2)
        pygame.draw.line(self.screen, COLOR_CYAN, (box_x, box_y), (box_x, box_y + tick_len), 2)
        pygame.draw.line(self.screen, COLOR_CYAN, (box_x + box_w - 1, box_y), (box_x + box_w - 1 - tick_len, box_y), 2)
        pygame.draw.line(self.screen, COLOR_CYAN, (box_x + box_w - 1, box_y), (box_x + box_w - 1, box_y + tick_len), 2)

        # ==========================================
        # COLUMN 1: NAV & FLIGHT
        # ==========================================
        y = start_y

        self.screen.blit(font.render("[NAV-COM]", True, COLOR_DIM), (col1_x, y))
        y += line_h

        pos_str = f"POS X:{int(ship.pos_x):+06d} Y:{int(ship.pos_y):+06d}"
        self.screen.blit(font.render(pos_str, True, COLOR_CYAN), (col1_x, y))
        y += line_h

        vel_str = f"VEL X:{ship.vel_x:+04.1f} Y:{ship.vel_y:+04.1f} [{ship.total_velocity:03.0f}u]"
        self.screen.blit(font.render(vel_str, True, COLOR_CYAN), (col1_x, y))
        y += line_h

        hdg_str = f"HDG {int(ship.heading) % 360:03d} DEG"
        self.screen.blit(font.render(hdg_str, True, COLOR_CYAN), (col1_x, y))

        # ==========================================
        # COLUMN 2: HARDWARE & CONTROL
        # ==========================================
        y = start_y

        self.screen.blit(font.render("[SUBSYSTEMS]", True, COLOR_DIM), (col2_x, y))
        y += line_h

        # Integrated Manual/Auto Control Indicator
        ctrl_enabled = getattr(ship, "manual_control", False)
        ctrl_stat = "MANUAL" if ctrl_enabled else "AUTO  "
        ctrl_color = COLOR_CYAN if ctrl_enabled else COLOR_DIM

        ctrl_surf = font.render(f"FLT MODE   [{ctrl_stat}]", True, ctrl_color)
        self.screen.blit(ctrl_surf, (col2_x, y))

        # Glowing LED indicator dot aligned right next to the text status
        led_x = col2_x + ctrl_surf.get_width() + 10
        led_y = y + (line_h // 2) - 1
        pygame.draw.circle(self.screen, ctrl_color, (led_x, led_y), 4)
        if ctrl_enabled:
            pygame.draw.circle(self.screen, (255, 255, 255), (led_x, led_y), 2)  # Hot core
        y += line_h

        damp_stat = "ON " if getattr(ship, "dampening", True) else "OFF"
        damp_color = COLOR_CYAN if getattr(ship, "dampening", True) else COLOR_DIM
        self.screen.blit(
            font.render(f"INERT DAMP  [{damp_stat}]", True, damp_color), (col2_x, y)
        )
        y += line_h

        laser_stat = "ACT" if getattr(ship, "laser_on", False) else "OFF"
        laser_color = COLOR_CYAN if getattr(ship, "laser_on", False) else COLOR_DIM
        self.screen.blit(
            font.render(f"BEAM LASER  [{laser_stat}]", True, laser_color), (col2_x, y)
        )
        y += line_h

        # Close-Range Scanner Status
        crs_active = getattr(ship, "close_range_scanning", False)
        crs_contacts = len(getattr(ship, "confirmed_signatures", []))
        crs_stat = "ON" if crs_active else "OFF"
        crs_color = COLOR_CYAN if crs_active else COLOR_DIM
        self.screen.blit(
            font.render(f"PROX SCAN   [{crs_stat}] ({crs_contacts} sig)", True, crs_color), (col2_x, y)
        )

        # ==========================================
        # COLUMN 3: ORDNANCE & TACTICAL
        # ==========================================
        y = start_y

        self.screen.blit(font.render("[TACTICAL]", True, COLOR_DIM), (col3_x, y))
        y += line_h

        if ship.missile_cooling_down:
            m_str = f"MSL [{ship.total_missiles:02d}] RCHG ({ship.missile_cooldown_timer:.1f}s)"
            m_color = COLOR_AMBER
        else:
            m_str = f"MSL [{ship.total_missiles:02d}] READY"
            m_color = COLOR_CYAN
        self.screen.blit(font.render(m_str, True, m_color), (col3_x, y))
        y += line_h

        # Health Status
        health = getattr(ship, "health", 5)
        health = int(health)
        health_color = COLOR_RED if health <= 2 else (COLOR_AMBER if health <= 3 else COLOR_CYAN)
        self.screen.blit(
            font.render(f"HULL INTEGRITY [{health}]", True, health_color), (col3_x, y)
        )
        y += line_h

        if ship.painted or ship.enemy_has_missile_solution:
            threat_str = "! LOCK DETECTED !" if ship.enemy_has_missile_solution else "! RADAR PAINTED !"
            self.screen.blit(font.render(threat_str, True, COLOR_RED), (col3_x, y))
        elif ship.has_missile_solution:
            self.screen.blit(
                font.render("> TGT LOCK ACQUIRED <", True, COLOR_AMBER), (col3_x, y)
            )
        else:
            self.screen.blit(
                font.render("NO THREAT LOCKS", True, COLOR_DIM), (col3_x, y)
            )

    def draw_ui_layout(self):
        """Draw UI panel backgrounds and borders with clean CRT chassis framing."""
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # Define panel rects
        top_panel = pygame.Rect(0, 0, screen_width, self.THIN_HEIGHT)
        bottom_panel = pygame.Rect(
            0, screen_height - self.THIN_HEIGHT, screen_width, self.THIN_HEIGHT
        )
        left_panel = pygame.Rect(
            0, self.THIN_HEIGHT, self.PANEL_WIDTH, screen_height - 2 * self.THIN_HEIGHT
        )
        right_panel = pygame.Rect(
            screen_width - self.PANEL_WIDTH,
            self.THIN_HEIGHT,
            self.PANEL_WIDTH,
            screen_height - 2 * self.THIN_HEIGHT,
        )

        panels = [top_panel, bottom_panel, left_panel, right_panel]

        # 1. Base Background Fill
        for panel in panels:
            pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, panel)

        # 2. Primary Outer Borders
        for panel in panels:
            pygame.draw.rect(self.screen, self.COLOR_BORDER_PRIMARY, panel, 2)

        # 3. Parallel Inset Line (Recessed Chassis Effect)
        for panel in panels:
            inner_rect = panel.inflate(-10, -10)
            pygame.draw.rect(self.screen, self.COLOR_BORDER_INSET, inner_rect, 1)

        # 4. Viewport Corner Notch Ticks
        v_left = self.PANEL_WIDTH
        v_right = screen_width - self.PANEL_WIDTH
        v_top = self.THIN_HEIGHT
        v_bottom = screen_height - self.THIN_HEIGHT

        # Top-Left Notch
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_left, v_top),
            (v_left + self.NOTCH_LENGTH, v_top), self.NOTCH_WIDTH
        )
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_left, v_top),
            (v_left, v_top + self.NOTCH_LENGTH), self.NOTCH_WIDTH
        )

        # Top-Right Notch
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_right, v_top),
            (v_right - self.NOTCH_LENGTH, v_top), self.NOTCH_WIDTH
        )
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_right, v_top),
            (v_right, v_top + self.NOTCH_LENGTH), self.NOTCH_WIDTH
        )

        # Bottom-Left Notch
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_left, v_bottom),
            (v_left + self.NOTCH_LENGTH, v_bottom), self.NOTCH_WIDTH
        )
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_left, v_bottom),
            (v_left, v_bottom - self.NOTCH_LENGTH), self.NOTCH_WIDTH
        )

        # Bottom-Right Notch
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_right, v_bottom),
            (v_right - self.NOTCH_LENGTH, v_bottom), self.NOTCH_WIDTH
        )
        pygame.draw.line(
            self.screen, self.COLOR_CORNER_ACCENT, (v_right, v_bottom),
            (v_right, v_bottom - self.NOTCH_LENGTH), self.NOTCH_WIDTH
        )

    def draw_ui_ftl_override(self, ftl_jumping):
        """Draw simple FTL JUMPING text boxes that fade out.

        Args:
            ftl_jumping: Boolean indicating if FTL jump is active
        """
        if not ftl_jumping:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # Panel geometry
        top_panel = pygame.Rect(0, 0, screen_width, self.THIN_HEIGHT)
        bottom_panel = pygame.Rect(
            0, screen_height - self.THIN_HEIGHT, screen_width, self.THIN_HEIGHT
        )
        left_panel = pygame.Rect(
            0, self.THIN_HEIGHT, self.PANEL_WIDTH, screen_height - 2 * self.THIN_HEIGHT
        )
        right_panel = pygame.Rect(
            screen_width - self.PANEL_WIDTH,
            self.THIN_HEIGHT,
            self.PANEL_WIDTH,
            screen_height - 2 * self.THIN_HEIGHT,
        )

        COLOR_PHOSPHOR = (0, 255, 65)
        COLOR_BLACK = (0, 0, 0)

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
            self.font_crt = pygame.font.Font(None, 20)

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

    def draw_scanlines(self):  # noqa
        scanline_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)

        for y in range(0, self.screen.get_height(), self.SCANLINE_SPACING):
            pygame.draw.line(
                scanline_surface,
                self.COLOR_SCANLINE,
                (0, y),
                (self.screen.get_width(), y),
                self.SCANLINE_HEIGHT
            )

        scanline_surface.set_alpha(self.SCANLINE_ALPHA)
        self.screen.blit(scanline_surface, (0, 0))

    def draw_world_grid(self, camera_x, camera_y, show_grid=True):
        """Draw coordinate grid overlay in world space.

        Args:
            camera_x: Camera X position
            camera_y: Camera Y position
            show_grid: Boolean to toggle grid on/off
        """
        if not show_grid:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # World area bounds
        world_left = self.PANEL_WIDTH
        world_right = screen_width - self.PANEL_WIDTH
        world_top = self.THIN_HEIGHT
        world_bottom = screen_height - self.THIN_HEIGHT

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

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # World area bounds
        world_left = self.PANEL_WIDTH
        world_right = screen_width - self.PANEL_WIDTH
        world_top = self.THIN_HEIGHT
        world_bottom = screen_height - self.THIN_HEIGHT

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
            # Draw red corner brackets in all 4 corners of viewport
            bracket_size = 20
            bracket_width = 2
            bracket_color = (255, 100, 100)

            # Top-Left
            pygame.draw.line(self.screen, bracket_color,
                             (world_left, world_top), (world_left + bracket_size, world_top), bracket_width)
            pygame.draw.line(self.screen, bracket_color,
                             (world_left, world_top), (world_left, world_top + bracket_size), bracket_width)

            # Top-Right
            pygame.draw.line(self.screen, bracket_color,
                             (world_right, world_top), (world_right - bracket_size, world_top), bracket_width)
            pygame.draw.line(self.screen, bracket_color,
                             (world_right, world_top), (world_right, world_top + bracket_size), bracket_width)

            # Bottom-Left
            pygame.draw.line(self.screen, bracket_color,
                             (world_left, world_bottom), (world_left + bracket_size, world_bottom), bracket_width)
            pygame.draw.line(self.screen, bracket_color,
                             (world_left, world_bottom), (world_left, world_bottom - bracket_size), bracket_width)

            # Bottom-Right
            pygame.draw.line(self.screen, bracket_color,
                             (world_right, world_bottom), (world_right - bracket_size, world_bottom), bracket_width)
            pygame.draw.line(self.screen, bracket_color,
                             (world_right, world_bottom), (world_right, world_bottom - bracket_size), bracket_width)

            # Warning text in top-right corner
            warning_text = self.font_body.render("LASER LOCK DETECTED", True, (255, 100, 100))
            self.screen.blit(warning_text, (world_right - warning_text.get_width() - 20, world_top + 20))

    def draw_radar(self, player_ship, signatures, is_scanning=False):
        radar_x, radar_y, radar_size = self._get_radar_bounds()
        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2

        # FIX: Max radius is half the bounding box, not the full bounding box
        max_radius = radar_size // 2

        # --- CRT Phosphor Background & Scanlines ---
        pygame.draw.rect(self.screen, (5, 10, 5), radar_rect)  # Deep murky green background

        # Faux CRT scanlines
        for y in range(radar_y, radar_y + radar_size, 4):
            pygame.draw.line(self.screen, (10, 25, 10), (radar_x, y), (radar_x + radar_size, y))

        # --- Arcade Corner Brackets (Replaces plain border) ---
        b_len = 15
        b_color = self.COLOR_HUD_AMBER
        # Top-Left
        pygame.draw.line(self.screen, b_color, (radar_x, radar_y), (radar_x + b_len, radar_y), 2)
        pygame.draw.line(self.screen, b_color, (radar_x, radar_y), (radar_x, radar_y + b_len), 2)
        # Top-Right
        pygame.draw.line(self.screen, b_color, (radar_x + radar_size, radar_y), (radar_x + radar_size - b_len, radar_y), 2)
        pygame.draw.line(self.screen, b_color, (radar_x + radar_size, radar_y), (radar_x + radar_size, radar_y + b_len), 2)
        # Bottom-Left
        pygame.draw.line(self.screen, b_color, (radar_x, radar_y + radar_size), (radar_x + b_len, radar_y + radar_size), 2)
        pygame.draw.line(self.screen, b_color, (radar_x, radar_y + radar_size), (radar_x, radar_y + radar_size - b_len), 2)
        # Bottom-Right
        pygame.draw.line(self.screen, b_color, (radar_x + radar_size, radar_y + radar_size), (radar_x + radar_size - b_len, radar_y + radar_size), 2)
        pygame.draw.line(self.screen, b_color, (radar_x + radar_size, radar_y + radar_size), (radar_x + radar_size, radar_y + radar_size - b_len), 2)

        # --- Tactical Grid ---
        # Hardware clip prevents edge blips or grid lines from ever drawing outside the radar box
        old_clip = self.screen.get_clip()
        self.screen.set_clip(radar_rect)

        grid_color = (40, 100, 40)  # Glowing dim green
        grid_spacing = max_radius // self.RADAR_GRID_COUNT

        # Axis Crosshairs
        pygame.draw.line(self.screen, grid_color, (radar_x, center_y), (radar_x + radar_size, center_y), 1)
        pygame.draw.line(self.screen, grid_color, (center_x, radar_y), (center_x, radar_y + radar_size), 1)

        # Distance Rings
        for i in range(1, self.RADAR_GRID_COUNT + 1):
            offset = grid_spacing * i
            pygame.draw.circle(self.screen, grid_color, (center_x, center_y), offset, 1)

        # Player position (Glowing cluster)
        pygame.draw.circle(self.screen, (0, 255, 0), (center_x, center_y), 3)
        pygame.draw.rect(self.screen, (200, 255, 200), (center_x - 1, center_y - 1, 3, 3))  # Hot core

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
            pygame.draw.rect(self.screen, (255, 255, 255), (radar_px - 1, radar_py - 1, 2, 2))  # White hot center

        # Restore rendering area
        self.screen.set_clip(old_clip)

        # --- Blinking Retro Label ---
        show_label = True
        if is_scanning:
            # Blink every ~500ms
            show_label = (pygame.time.get_ticks() // 500) % 2 == 0

        if show_label:
            label_text = "RADAR [ SCANNING... ]" if is_scanning else "RADAR"
            label_color = self.COLOR_HUD_CYAN if is_scanning else self.COLOR_HUD_AMBER
            label = self.font_radar_label.render(label_text, True, label_color)

            label_bg = pygame.Rect(radar_x + 8, radar_y + 8, label.get_width() + 6, label.get_height() + 2)
            pygame.draw.rect(self.screen, (0, 0, 0), label_bg)  # Solid black background behind text
            pygame.draw.rect(self.screen, label_color, label_bg, 1)  # Thin neon border around text
            self.screen.blit(label, (radar_x + 11, radar_y + 9))

    def draw_laser(self, laser, laser_endpoint, camera_x, camera_y, active):
        if not active:
            return
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()
        radar_x, radar_y, radar_size = self._get_radar_bounds()

        origin_x, origin_y = laser.ship_of_origin.rect.center
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
        pygame.draw.line(self.screen, (255, 255, 255), screen_origin, screen_end, 1)

        # Impact flare at the endpoint
        pygame.draw.circle(self.screen, (255, 255, 255), screen_end, 2)
        pygame.draw.circle(self.screen, beam_color, screen_end, 4, 1)

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
        pygame.draw.rect(self.screen, (255, 255, 255), (radar_end_x - 1, radar_end_y - 1, 2, 2))

        self.screen.set_clip(None)

    def draw_laser_targeting_info(self, target_type: str, laser_assessor, enabled: bool):
        """Draw laser targeting assessment status below the radar panel.

        Args:
            target_type: String classification of the target
            laser_assessor: LaserAssessor object with lock info
            enabled: Boolean indicating if laser targeting is active
        """

        radar_x, radar_y, radar_size = self._get_radar_bounds()

        # Position box directly under the radar face
        box_x = radar_x
        box_y = radar_y + radar_size + 15
        box_w = radar_size
        box_h = 60

        border_color = self.COLOR_HUD_AMBER if enabled else (80, 60, 0)

        # Container Box
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, box_rect)
        pygame.draw.rect(self.screen, border_color, box_rect, 1)

        # Header Label
        header = self.font_tiny.render("LASER TARGET ANALYSIS", True, (150, 150, 100))
        self.screen.blit(header, (box_x + 8, box_y + 6))

        # Status Line 1: Classification
        if enabled:
            text_str1 = f"CLASSIFICATION: {target_type.upper()}"
            color1 = self.COLOR_HUD_CYAN if target_type != "Nothing" else (200, 100, 50)
        else:
            text_str1 = "TARGETING SYSTEM INACTIVE"
            color1 = (200, 50, 50)

        status_surface1 = self.font_body.render(text_str1, True, color1)
        self.screen.blit(status_surface1, (box_x + 8, box_y + 20))

        # Status Line 2: Lock status
        if enabled:
            if laser_assessor.laser_locked:
                text_str2 = "STATUS: LOCK ACQUIRED"
                color2 = (100, 255, 100)
            elif target_type != "Nothing":
                text_str2 = "STATUS: TRACKING [SPACE TO LOCK]"
                color2 = self.COLOR_HUD_AMBER
            else:
                text_str2 = "STATUS: SEARCHING"
                color2 = (150, 150, 150)
        else:
            text_str2 = "SYSTEM OFFLINE"
            color2 = (200, 50, 50)

        status_surface2 = self.font_body.render(text_str2, True, color2)
        self.screen.blit(status_surface2, (box_x + 8, box_y + 38))

    def draw_missile_vectors(self, player_id, missiles, camera_x, camera_y):
        world_left, world_right, world_top, world_bottom = self._get_world_bounds()

        # Viewport center (reference origin for edge projection)
        center_x = (world_left + world_right) / 2
        center_y = (world_top + world_bottom) / 2

        enemy_missiles = [
            m for m in missiles
            if getattr(m, "contact", None) and m.contact.player_id == player_id
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

                # Target Lock Bracket Box at Edge Anchor
                hx, hy = edge_x, edge_y

                # Top-Left corner
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx - self.MISSILE_LOCK_BOX_SIZE, hy - self.MISSILE_LOCK_BOX_SIZE),
                    (hx - self.MISSILE_LOCK_BOX_SIZE + 5, hy - self.MISSILE_LOCK_BOX_SIZE), 2
                )
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx - self.MISSILE_LOCK_BOX_SIZE, hy - self.MISSILE_LOCK_BOX_SIZE),
                    (hx - self.MISSILE_LOCK_BOX_SIZE, hy - self.MISSILE_LOCK_BOX_SIZE + 5), 2
                )

                # Top-Right corner
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx + self.MISSILE_LOCK_BOX_SIZE, hy - self.MISSILE_LOCK_BOX_SIZE),
                    (hx + self.MISSILE_LOCK_BOX_SIZE - 5, hy - self.MISSILE_LOCK_BOX_SIZE), 2
                )
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx + self.MISSILE_LOCK_BOX_SIZE, hy - self.MISSILE_LOCK_BOX_SIZE),
                    (hx + self.MISSILE_LOCK_BOX_SIZE, hy - self.MISSILE_LOCK_BOX_SIZE + 5), 2
                )

                # Bottom-Left corner
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx - self.MISSILE_LOCK_BOX_SIZE, hy + self.MISSILE_LOCK_BOX_SIZE),
                    (hx - self.MISSILE_LOCK_BOX_SIZE + 5, hy + self.MISSILE_LOCK_BOX_SIZE), 2
                )
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx - self.MISSILE_LOCK_BOX_SIZE, hy + self.MISSILE_LOCK_BOX_SIZE),
                    (hx - self.MISSILE_LOCK_BOX_SIZE, hy + self.MISSILE_LOCK_BOX_SIZE - 5), 2
                )

                # Bottom-Right corner
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx + self.MISSILE_LOCK_BOX_SIZE, hy + self.MISSILE_LOCK_BOX_SIZE),
                    (hx + self.MISSILE_LOCK_BOX_SIZE - 5, hy + self.MISSILE_LOCK_BOX_SIZE), 2
                )
                pygame.draw.line(
                    self.screen, self.COLOR_MISSILE_LOCK,
                    (hx + self.MISSILE_LOCK_BOX_SIZE, hy + self.MISSILE_LOCK_BOX_SIZE),
                    (hx + self.MISSILE_LOCK_BOX_SIZE, hy + self.MISSILE_LOCK_BOX_SIZE - 5), 2
                )

    def draw_tactical_map(self, active, player_ship, confirmed_contacts, scan_active=False, scan_range=1000, laser_active=False, laser_direction=0, laser_locked=False, locked_object=None):
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
        pygame.draw.rect(self.screen, self.COLOR_DFS_BORDER, map_rect, 2)

        previous_clip = self.screen.get_clip()
        self.screen.set_clip(map_rect)

        map_center = map_rect.center
        max_display_range = 5000

        player_x, player_y = player_ship.rect.center
        scale = min(map_rect.width, map_rect.height) / (max_display_range * 2)

        def world_to_screen(wx, wy):
            """World coords (relative to player) to map panel pixels."""
            return map_center[0] + wx * scale, map_center[1] + wy * scale

        # --- WORLD GRID (DIMMED) ---
        grid_color = (30, 40, 50)
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
        pygame.draw.polygon(self.screen, (100, 30, 30), boundary_pts, 1)

        # --- CLOSE-RANGE SCAN RADIUS ---
        if scan_active:
            radius_px = scan_range * scale
            pygame.draw.circle(self.screen, (0, 220, 220, 40), map_center, int(radius_px))
            pygame.draw.circle(self.screen, (0, 220, 220, 100), map_center, int(radius_px), 1)

        # --- LASER BEAM ---
        if laser_active:
            rad = math.radians(laser_direction - 90)
            beam_end_x = math.cos(rad) * LASER_RANGE
            beam_end_y = math.sin(rad) * LASER_RANGE

            beam_start = world_to_screen(0, 0)
            beam_end = world_to_screen(beam_end_x, beam_end_y)

            # Beam color changes if locked
            beam_color = (255, 100, 100) if laser_locked else (255, 150, 0)
            pygame.draw.line(self.screen, beam_color, beam_start, beam_end, 2)

            # Highlight locked target with red circle
            if laser_locked and locked_object:
                obj_x = getattr(locked_object, 'pos_x', None) or locked_object.rect.center[0]
                obj_y = getattr(locked_object, 'pos_y', None) or locked_object.rect.center[1]
                lock_screen = world_to_screen(obj_x - player_x, obj_y - player_y)
                pygame.draw.circle(self.screen, (255, 100, 100), lock_screen, 12, 2)

        # --- CONFIRMED CONTACTS (With Confidence Fading) ---
        for pos_x, pos_y, contact_type, velocity, confidence in confirmed_contacts:
            screen_x, screen_y = world_to_screen(pos_x - player_x, pos_y - player_y)

            # Size and color scale with confidence
            marker_size = max(2, int(3 + confidence * 6))
            alpha = int(255 * confidence)
            color = self.COLOR_DFS_CYAN
            drone_color = (220, 220, 50)
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

        # --- PLAYER CENTER ---
        pygame.draw.circle(self.screen, self.COLOR_DFS_AMBER, map_center, 5)

        self.screen.set_clip(previous_clip)

        # --- HEADER & FOOTER ---
        header = "TACTICAL MAP"
        txt_header = self.font_scan_body.render(header, True, self.COLOR_DFS_AMBER)
        self.screen.blit(txt_header, (map_rect.x + 15, map_rect.y + 12))

        contact_count = len(confirmed_contacts)
        moving_count = sum(1 for c in confirmed_contacts if c[3][0] != 0 or c[3][1] != 0)
        avg_confidence = (sum(c[4] for c in confirmed_contacts) / contact_count * 100) if contact_count > 0 else 0

        footer = f"CONFIRMED: {contact_count}  MOVING: {moving_count}  SIGNAL: {int(avg_confidence)}%"
        txt_footer = self.font_scan_body.render(footer, True, self.COLOR_DFS_CYAN)
        self.screen.blit(txt_footer, (map_rect.x + 15, map_rect.bottom - 35))

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
            vignette_color = (255, 60, 60, 25)  # Lower alpha
            pygame.draw.rect(vignette_surface, vignette_color, (0, 0, screen_width, screen_height))
            self.screen.blit(vignette_surface, (0, 0))

            # Small red X in corners only (not full viewport)
            x_color = (255, 80, 80)
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
            pygame.draw.rect(self.screen, (255, 100, 100),
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

        scan_color = (0, 255, 100, alpha)

        # Draw expanding concentric circles (scan sweep effect)
        max_radius = 150
        radius = int(max_radius * pulse)

        scan_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        pygame.draw.circle(scan_surface, scan_color, (center_x, center_y), radius, 2)
        pygame.draw.circle(scan_surface, scan_color, (center_x, center_y), max(radius - 20, 0), 1)
        self.screen.blit(scan_surface, (0, 0))

        # Corner warning indicators
        indicator_color = (0, 255, 100)
        indicator_size = 8
        pygame.draw.circle(self.screen, indicator_color, (world_left + 15, world_top + 15), indicator_size, 2)
        pygame.draw.circle(self.screen, indicator_color, (world_right - 15, world_top + 15), indicator_size, 2)

        # Warning text in center
        warning_text = self.font_scan_body.render("DFS SWEEP DETECTED!", True, (255, 50, 50))
        text_rect = warning_text.get_rect(center=(center_x, center_y + 80))
        self.screen.blit(warning_text, text_rect)

    def draw_deep_field_panel(self, contacts, direction_index, system_online=True):
        screen_height = self.screen.get_height()

        # Panel Geometry
        panel_x = self.DFS_PANEL_MARGIN
        panel_width = 560
        panel_y = self.THIN_HEIGHT + self.DFS_PANEL_MARGIN
        panel_height = (
                screen_height - panel_y - self.THIN_HEIGHT - self.DFS_PANEL_MARGIN
        )

        # Offline Mode
        if not system_online:
            rect = pygame.Rect(panel_x, panel_y, panel_width, 60)
            pygame.draw.rect(self.screen, self.COLOR_DFS_BG, rect)
            pygame.draw.rect(self.screen, self.COLOR_DFS_RED, rect, 2)

            txt = self.font_scan_header.render(
                "DEEP FIELD SCAN // OFFLINE", True, self.COLOR_DFS_RED
            )
            self.screen.blit(txt, (panel_x + 15, panel_y + 15))
            return

        # Active Panel
        rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        pygame.draw.rect(self.screen, self.COLOR_DFS_BG, rect)
        pygame.draw.rect(self.screen, self.COLOR_DFS_BORDER, rect, 2)
        pygame.draw.rect(self.screen, self.COLOR_DFS_INSET, rect.inflate(-8, -8), 1)

        # Direction
        directions = [
            ("N", "000"), ("NE", "045"), ("E", "090"), ("SE", "135"),
            ("S", "180"), ("SW", "225"), ("W", "270"), ("NW", "315"),
        ]
        direction, degrees = directions[direction_index % 8]

        x = panel_x + 15
        y = panel_y + 12

        # Header
        title = self.font_scan_header.render(
            f"DEEP FIELD SCAN // {direction} {degrees}°", True, self.COLOR_DFS_AMBER
        )
        self.screen.blit(title, (x, y))

        online = self.font_scan_body.render("● ONLINE", True, self.COLOR_DFS_GREEN)
        self.screen.blit(online, (panel_x + panel_width - 125, y + 5))

        y += 45
        pygame.draw.line(
            self.screen, self.COLOR_DFS_BORDER,
            (x, y), (panel_x + panel_width - 15, y)
        )

        # Summary Statistics
        y += 20
        total_contacts = len(contacts)
        moving_count = sum(1 for c in contacts if c[2])
        static_count = total_contacts - moving_count

        # Contact count
        summary_txt = self.font_scan_body.render(
            f"CONTACTS: {total_contacts}", True, self.COLOR_DFS_CYAN
        )
        self.screen.blit(summary_txt, (x, y))
        y += 28

        # Motion split
        motion_txt = self.font_scan_body.render(
            f"MOVING: {moving_count}    STATIONARY: {static_count}",
            True, self.COLOR_DFS_WHITE
        )
        self.screen.blit(motion_txt, (x, y))
        y += 28

        # Confidence breakdown
        high_conf = sum(1 for c in contacts if c[3] >= 0.75)
        med_conf = sum(1 for c in contacts if 0.5 <= c[3] < 0.75)
        low_conf = sum(1 for c in contacts if c[3] < 0.5)

        conf_txt = self.font_scan_body.render(
            f"CONFIDENCE: {high_conf} HIGH | {med_conf} MED | {low_conf} LOW",
            True, self.COLOR_DFS_AMBER
        )
        self.screen.blit(conf_txt, (x, y))

        y += 50
        pygame.draw.line(
            self.screen, self.COLOR_DFS_INSET,
            (x, y), (panel_x + panel_width - 15, y)
        )

        # Moving Contacts List
        y += 20
        if moving_count > 0:
            heading = self.font_scan_body.render("MOVING CONTACTS:", True, self.COLOR_DFS_GREEN)
            self.screen.blit(heading, (x, y))
            y += 28

            moving_contacts = sorted([c for c in contacts if c[2]], key=lambda c: c[3], reverse=True)

            for rng, ctype, _, confidence, _ in moving_contacts:
                conf_level = "HIGH" if confidence >= 0.75 else "MED" if confidence >= 0.5 else "LOW"
                line = f"  {ctype.upper():10} [{conf_level} {int(confidence * 100)}%]"

                txt = self.font_scan_body.render(line, True, self.COLOR_DFS_YELLOW)
                self.screen.blit(txt, (x, y))
                y += 25
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

        amber_color = getattr(self, 'COLOR_DFS_AMBER', (255, 170, 0))
        # Orange color for the radar scan projection lines
        orange_color = getattr(self, 'COLOR_DFS_ORANGE', (255, 120, 0))

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

    def draw_pirate_fire_warning(self, pirate_firing):
        """Draw a single orange line sweeping left to right across viewport.

        Args:
            pirate_firing: Boolean indicating if pirates have lock and are firing
        """
        if not pirate_firing:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # UI panel dimensions
        panel_width = 600
        thin_height = 200

        # World area bounds
        world_left = panel_width
        world_right = screen_width - panel_width
        world_top = thin_height
        world_bottom = screen_height - thin_height

        viewport_width = world_right - world_left
        viewport_height = world_bottom - world_top

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
        color = (brightness, brightness // 3, 0)

        # Draw vertical line
        import pygame
        pygame.draw.line(self.screen, color,
                         (line_x, world_top),
                         (line_x, world_bottom),
                         2)

        # Draw "PIRATE LOCK" text at top center
        if not hasattr(self, 'font_pirate_lock'):
            self.font_pirate_lock = pygame.font.Font(None, 24)

        warning_text = self.font_pirate_lock.render("PIRATE LOCK", True, color)
        text_x = screen_width // 2 - warning_text.get_width() // 2
        text_y = world_top + 15
        self.screen.blit(warning_text, (text_x, text_y))

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

    def draw_low_health_warning(self, low_health):
        """Draw flashing red warning box in bottom left of viewport.

        Args:
            low_health: Boolean indicating if ship is at low health
        """
        if not low_health:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # UI panel dimensions
        panel_width = 600
        thin_height = 200

        # World area bounds
        world_left = panel_width
        world_bottom = screen_height - thin_height

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
            color = (255, 50, 50)

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
                self.font_critical = pygame.font.Font(None, 14)

            text = self.font_critical.render("HULL CRITICAL", True, color)
            text_x = box_x + (box_w - text.get_width()) // 2
            text_y = box_y + box_h - 18
            self.screen.blit(text, (text_x, text_y))
