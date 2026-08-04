import math
import pygame
from utility.constants import *


class DrawUI:
    # Panel Dimensions (locked, matches UI layout)
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

    def __init__(self, screen):
        self.screen = screen
        self.lock_blink_counter = 0

        # Initialize all fonts once
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

        # Anchor safely inside bottom panel area
        panel_y_top = screen_height - self.THIN_HEIGHT
        panel_offset_x = getattr(self, "PANEL_WIDTH", 0) + 12

        # Container Box Dimensions
        box_x = panel_offset_x
        box_y = panel_y_top + 6
        box_w = 720  # Expanded slightly to accommodate larger font
        box_h = self.THIN_HEIGHT - 12

        # UI Theme Colors
        COLOR_CYAN = getattr(self, "COLOR_HUD_CYAN", (0, 255, 255))
        COLOR_AMBER = getattr(self, "COLOR_HUD_YELLOW", (255, 180, 0))
        COLOR_RED = getattr(self, "COLOR_HUD_RED", (255, 60, 60))
        COLOR_BORDER = getattr(self, "COLOR_BORDER_INSET", (0, 150, 150))
        COLOR_BG = getattr(self, "COLOR_PANEL_BG", (10, 15, 20))
        COLOR_DIM = (0, 120, 120)

        # 1. UPGRADED FONT (Bigger, readable, retro monospaced)
        font = pygame.font.SysFont("monospace", 17, bold=True)

        # 2. VERTICAL CENTERING MATH
        # 4 lines of text
        line_h = font.get_height() + 2
        total_text_h = line_h * 4
        # Center text vertically within the box interior
        start_y = box_y + (box_h - total_text_h) // 2

        # 3. COLUMN POSITIONS (Balanced across box width)
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
        # COLUMN 2: HARDWARE & SUBSYSTEMS
        # ==========================================
        y = start_y

        self.screen.blit(font.render("[SUBSYSTEMS]", True, COLOR_DIM), (col2_x, y))
        y += line_h

        damp_stat = "ON " if ship.dampening else "OFF"
        damp_color = COLOR_CYAN if ship.dampening else COLOR_DIM
        self.screen.blit(
            font.render(f"INERT DAMP  [{damp_stat}]", True, damp_color), (col2_x, y)
        )
        y += line_h

        laser_stat = "ACT" if ship.laser_on else "OFF"
        laser_color = COLOR_CYAN if ship.laser_on else COLOR_DIM
        self.screen.blit(
            font.render(f"BEAM LASER [{laser_stat}]", True, laser_color), (col2_x, y)
        )
        y += line_h

        dfs_stat = "ACT" if ship.dfs_on else "OFF"
        dfs_color = COLOR_CYAN if ship.dfs_on else COLOR_DIM
        self.screen.blit(
            font.render(f"DFS RADAR  [{dfs_stat}]", True, dfs_color), (col2_x, y)
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

    def draw_manual_control_indicator(self, enabled):
        """Draw manual control status indicator in top right.

        Args:
            enabled: Boolean, True if manual control is active
        """
        screen_width = self.screen.get_width()
        x = screen_width - 290
        y = 30

        light_color = self.COLOR_HUD_CYAN if enabled else self.COLOR_THREAT_DIM

        # Draw indicator box
        box_rect = pygame.Rect(x, y, 260, 40)
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, box_rect)
        pygame.draw.rect(self.screen, self.COLOR_HUD_CYAN, box_rect, 1)

        # Draw light indicator (circle)
        light_x, light_y = x + 20, y + 20
        pygame.draw.circle(self.screen, light_color, (light_x, light_y), 8)

        # Draw text
        status_text = "MANUAL CTRL" if enabled else "AUTO MODE"
        text = self.font_body.render(status_text, True, self.COLOR_HUD_CYAN)
        self.screen.blit(text, (x + 40, y + 8))

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

    def draw_radar(self, player_ship, signatures, is_scanning=False):
        radar_x, radar_y, radar_size = self._get_radar_bounds()

        # Draw radar background & border
        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        pygame.draw.rect(self.screen, (10, 20, 10), radar_rect)
        pygame.draw.rect(self.screen, self.COLOR_HUD_AMBER, radar_rect, 2)

        # Draw center crosshair (player position)
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2
        pygame.draw.circle(self.screen, (0, 255, 0), (center_x, center_y), 5)

        # Draw range grid
        grid_spacing = radar_size // self.RADAR_GRID_COUNT
        for i in range(1, self.RADAR_GRID_COUNT + 1):
            offset = grid_spacing * i
            pygame.draw.circle(self.screen, (80, 80, 60), (center_x, center_y), offset, 1)

        # Scale world coordinates to radar
        radar_scale = radar_size / self.RADAR_SCALE

        # Plot signatures
        player_x, player_y = player_ship.rect.center
        for sig_x, sig_y, color in signatures:
            rel_x = sig_x - player_x
            rel_y = sig_y - player_y

            radar_px = center_x + rel_x * radar_scale
            radar_py = center_y + rel_y * radar_scale

            if radar_x < radar_px < radar_x + radar_size and radar_y < radar_py < radar_y + radar_size:
                pygame.draw.circle(self.screen, color, (int(radar_px), int(radar_py)), 2)

        # Radar label with background
        label_text = "RADAR [ SCANNING... ]" if is_scanning else "RADAR"
        label_color = self.COLOR_HUD_CYAN if is_scanning else self.COLOR_HUD_AMBER
        label = self.font_radar_label.render(label_text, True, label_color)

        label_bg = pygame.Rect(radar_x + 8, radar_y + 8, label.get_width() + 6, label.get_height() + 2)
        pygame.draw.rect(self.screen, (10, 20, 10), label_bg)
        self.screen.blit(label, (radar_x + 11, radar_y + 9))

    def draw_laser(self, laser, laser_endpoint, camera_x, camera_y):
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
        pygame.draw.line(
            self.screen, beam_color,
            (origin_x - camera_x, origin_y - camera_y),
            (end_x - camera_x, end_y - camera_y),
            2
        )
        self.screen.set_clip(None)

        # --- 2. Radar panel beam ---
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2
        radar_scale = radar_size / self.RADAR_SCALE

        rel_x = end_x - origin_x
        rel_y = end_y - origin_y
        radar_end_x = center_x + rel_x * radar_scale
        radar_end_y = center_y + rel_y * radar_scale

        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        self.screen.set_clip(radar_rect)
        pygame.draw.line(
            self.screen, beam_color,
            (center_x, center_y),
            (radar_end_x, radar_end_y),
            1
        )
        self.screen.set_clip(None)

    def draw_laser_targeting_info(self, signature_type: str, enabled: bool):
        """Draw laser targeting assessment status below the radar panel.

        Args:
            signature_type: Text description of analyzed contact
            enabled: Boolean indicating if laser targeting is active
        """
        screen_width = self.screen.get_width()
        radar_x, radar_y, radar_size = self._get_radar_bounds()

        # Position box directly under the radar face
        box_x = radar_x
        box_y = radar_y + radar_size + 15
        box_w = radar_size
        box_h = 45

        border_color = self.COLOR_HUD_AMBER if enabled else (80, 60, 0)
        text_color = self.COLOR_HUD_CYAN if enabled else (200, 50, 50)

        # Container Box
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, box_rect)
        pygame.draw.rect(self.screen, border_color, box_rect, 1)

        # Header Label
        header = self.font_tiny.render("LASER TARGET ANALYSIS", True, (150, 150, 100))
        self.screen.blit(header, (box_x + 8, box_y + 6))

        # Status Line
        if enabled:
            text_str = f"CLASSIFICATION: {signature_type.upper()}"
        else:
            text_str = "TARGETING SYSTEM INACTIVE"

        status_surface = self.font_body.render(text_str, True, text_color)
        self.screen.blit(status_surface, (box_x + 8, box_y + 20))

    def draw_missile_vectors(self, player_id, missiles, camera_x, camera_y):
        """Draw incoming missile trajectory vectors with screen-space alignment.

        Draws high-visibility vector lines anchored at screen edges.
        """
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

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

    def draw_tactical_map(self, active, player_ship, confirmed_contacts):
        """Draw tactical map showing confirmed contacts with confidence fading.

        Args:
            active: Boolean indicating if the map display is active.
            player_ship: Player ship object.
            confirmed_contacts: List of (pos_x, pos_y, contact_type, velocity_tuple, confidence) tuples.
        """
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
            return (map_center[0] + wx * scale, map_center[1] + wy * scale)

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

    # Deep field scan stuff

    def draw_deep_field_panel(self, contacts, direction_index, system_online=True):
        """Draw tactical deep field sensor display with minimal summary.

        Args:
            contacts: List of (range_km, contact_type, is_moving, confidence) tuples
            direction_index: 0-7 scan direction (0=N, 1=NE, etc.)
            system_online: Whether the deep field scanner is active
        """
        screen_width = self.screen.get_width()
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

    def draw_dfs_corridor(self, player_ship, dfs_direction_index, camera_x, camera_y):
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
