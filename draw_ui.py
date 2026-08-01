import math

import pygame

from constants import GRID_SIZE


class DrawUI:
    def __init__(self, screen):
        self.lock_blink_counter = 0
        self.font_small = None
        self.screen = screen

        self.font = pygame.font.Font(None, 28)  # Was 18
        self.font_small = pygame.font.Font(None, 35)  # Was 16

    def draw_ship_info(self, ship):
        """Draw ship status information in bottom left panel

        Args:
            ship: Ship object with pos_x, pos_y, vel_x, vel_y, total_missiles

        Future expansions:
            - Add health/armor values below missiles
            - Add heat/thermal signature
            - Add sensor status (active/passive)
            - Add damage indicators
        """
        x = 30
        y = self.screen.get_height() - 160
        line_height = 28  # Was 20

        # Title
        title = self.font_small.render("SHIP STATUS", True, (0, 255, 200))
        self.screen.blit(title, (x, y))
        y += line_height + 10

        # Position data
        pos_text = self.font_small.render(f"POS: {int(ship.pos_x)}, {int(ship.pos_y)}", True, (0, 255, 200))
        self.screen.blit(pos_text, (x, y))
        y += line_height

        # Velocity data
        vel_text = self.font_small.render(f"VEL: {ship.vel_x:.2f}, {ship.vel_y:.2f}", True, (0, 255, 200))
        self.screen.blit(vel_text, (x, y))
        y += line_height

        # Missiles remaining
        missile_text = self.font_small.render(f"MISSILES: {ship.total_missiles}", True, (0, 255, 200))
        self.screen.blit(missile_text, (x, y))

    def draw_weapon_solution_indicator(self, locked):
        """Draw weapon solution indicator in top left"""
        x = 30
        y = 30

        # Light color - green if locked, red if not
        light_color = (0, 255, 0) if locked else (150, 50, 50)

        # Draw indicator box
        box_rect = pygame.Rect(x, y, 260, 40)  # Was 180x25
        pygame.draw.rect(self.screen, (30, 30, 40), box_rect)
        pygame.draw.rect(self.screen, (0, 255, 200), box_rect, 1)

        # Draw light indicator (circle)
        light_x = x + 20
        light_y = y + 20
        pygame.draw.circle(self.screen, light_color, (light_x, light_y), 8)  # Was 6

        # Draw text
        text = self.font.render("WEAPON SOLUTION", True, (0, 255, 200))
        self.screen.blit(text, (x + 40, y + 8))

    def draw_manual_control_indicator(self, enabled):
        """Draw manual control status indicator in top right

        Args:
            enabled: Boolean, True if manual control is active

        Future expansions:
            - Add control mode indicators (sensor mode, targeting mode)
            - Add key bindings display
            - Add control sensitivity slider
        """
        screen_width = self.screen.get_width()
        x = screen_width - 290  # Position from right edge
        y = 30

        # Light color - cyan if enabled, red if not
        light_color = (0, 255, 200) if enabled else (150, 50, 50)

        # Draw indicator box
        box_rect = pygame.Rect(x, y, 260, 40)
        pygame.draw.rect(self.screen, (30, 30, 40), box_rect)
        pygame.draw.rect(self.screen, (0, 255, 200), box_rect, 1)

        # Draw light indicator (circle)
        light_x = x + 20
        light_y = y + 20
        pygame.draw.circle(self.screen, light_color, (light_x, light_y), 8)

        # Draw text
        status_text = "MANUAL CTRL" if enabled else "AUTO MODE"
        text = self.font.render(status_text, True, (0, 255, 200))
        self.screen.blit(text, (x + 40, y + 8))

    def draw_ui_layout(self):
        """Draw UI panel backgrounds and borders - retro CRT aesthetic"""
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        panel_width = 600
        thin_height = 200

        # Define panel areas
        top_panel = pygame.Rect(0, 0, screen_width, thin_height)
        bottom_panel = pygame.Rect(0, screen_height - thin_height, screen_width, thin_height)
        left_panel = pygame.Rect(0, thin_height, panel_width, screen_height - 2 * thin_height)
        right_panel = pygame.Rect(screen_width - panel_width, thin_height, panel_width, screen_height - 2 * thin_height)

        # Retro CRT colors - dark background with cyan accents
        panel_color = (2, 8, 2)
        border_color = (200, 150, 0)
        border_width = 2

        # Draw panel backgrounds
        pygame.draw.rect(self.screen, panel_color, top_panel)
        pygame.draw.rect(self.screen, panel_color, bottom_panel)
        pygame.draw.rect(self.screen, panel_color, left_panel)
        pygame.draw.rect(self.screen, panel_color, right_panel)

        # Draw borders
        pygame.draw.rect(self.screen, border_color, top_panel, border_width)
        pygame.draw.rect(self.screen, border_color, bottom_panel, border_width)
        pygame.draw.rect(self.screen, border_color, left_panel, border_width)
        pygame.draw.rect(self.screen, border_color, right_panel, border_width)

    def draw_scanlines(self): # noqa
        """Draw CRT scanlines with transparency""" # noqa
        scanline_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)

        line_height = 2
        line_spacing = 4

        for y in range(0, self.screen.get_height(), line_spacing):
            pygame.draw.line(
                scanline_surface,
                (0, 0, 0),
                (0, y),
                (self.screen.get_width(), y),
                line_height
            )

        scanline_surface.set_alpha(150)
        self.screen.blit(scanline_surface, (0, 0))

    def draw_world_grid(self, camera_x, camera_y, show_grid=True):
        """Draw coordinate grid overlay in world space

        Args:
            camera_x: Camera X position
            camera_y: Camera Y position
            show_grid: Boolean to toggle grid on/off

        Future expansions:
            - Adjustable grid size
            - Different grid densities
            - Color customization
        """
        if not show_grid:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # UI panel dimensions (must match draw_ui_layout)
        panel_width = 600
        thin_height = 200

        # World area bounds
        world_left = panel_width
        world_right = screen_width - panel_width
        world_top = thin_height
        world_bottom = screen_height - thin_height

        grid_size = GRID_SIZE # World units between grid lines
        grid_color = (100, 100, 80)  # Muted olive
        text_color = (150, 150, 100)

        if not hasattr(self, 'font_grid'):
            self.font_grid = pygame.font.Font(None, 14)

        # Calculate starting grid position in world space
        start_x = int(camera_x / grid_size) * grid_size
        start_y = int(camera_y / grid_size) * grid_size

        # Draw vertical grid lines
        x = start_x
        while x < camera_x + screen_width:
            screen_x = x - camera_x
            if world_left < screen_x < world_right:
                pygame.draw.line(self.screen, grid_color, (screen_x, world_top), (screen_x, world_bottom), 1)
                # Draw coordinate label
                label = self.font_grid.render(str(int(x)), True, text_color)
                self.screen.blit(label, (screen_x + 5, world_top + 5))
            x += grid_size

        # Draw horizontal grid lines
        y = start_y
        while y < camera_y + screen_height:
            screen_y = y - camera_y
            if world_top < screen_y < world_bottom:
                pygame.draw.line(self.screen, grid_color, (world_left, screen_y), (world_right, screen_y), 1)
                # Draw coordinate label
                label = self.font_grid.render(str(int(y)), True, text_color)
                self.screen.blit(label, (world_left + 5, screen_y + 5))
            y += grid_size

    def draw_missile_lock_warning(self, locked):
        if not locked:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # UI panel dimensions (must match draw_ui_layout)
        panel_width = 600
        thin_height = 200

        # World area bounds
        world_left = panel_width
        world_right = screen_width - panel_width
        world_top = thin_height
        world_bottom = screen_height - thin_height

        # Blink timing
        if not hasattr(self, 'lock_blink_counter'):
            self.lock_blink_counter = 0

        self.lock_blink_counter += 1
        blink_frequency = 10

        if (self.lock_blink_counter // blink_frequency) % 2 == 0:
            border_color = (255, 0, 0)
            border_width = 10

            # Draw red border around world area
            pygame.draw.rect(self.screen, border_color,
                             (world_left, world_top, world_right - world_left, world_bottom - world_top),
                             border_width)

    def draw_radar(self, player_ship, signatures):
        """Draw tactical radar in right panel

        Args:
            player_ship: Player ship object (pos_x, pos_y)
            signatures: List of (x, y) tuples representing contacts

        Future expansions:
            - Circular radar display instead of square
            - Color coding by contact type (ship vs decoy)
            - Range rings with distance labels
            - Contact age/fade effect
        """
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # UI panel dimensions
        panel_width = 600
        thin_height = 200

        # Right panel bounds - make radar fill most of it
        radar_x = screen_width - panel_width + 20
        radar_y = thin_height + 20
        radar_size = screen_height - 2 * thin_height - 40  # Fill vertical space

        # Make it square
        radar_size = min(radar_size, panel_width - 40)

        # Draw radar background
        radar_rect = pygame.Rect(radar_x, radar_y, radar_size, radar_size)
        pygame.draw.rect(self.screen, (10, 20, 10), radar_rect)
        pygame.draw.rect(self.screen, (200, 150, 0), radar_rect, 2)

        # Draw center crosshair (player position)
        center_x = radar_x + radar_size // 2
        center_y = radar_y + radar_size // 2
        pygame.draw.circle(self.screen, (0, 255, 0), (center_x, center_y), 5)

        # Draw range grid (larger rings now)
        grid_color = (80, 80, 60)
        grid_spacing = radar_size // 4
        for i in range(1, 3):
            offset = grid_spacing * i
            pygame.draw.circle(self.screen, grid_color, (center_x, center_y), offset, 1)

        # Scale world coordinates to radar (-2000 to +2000 world units = full radar)
        radar_scale = radar_size / 4000.0

        # Plot signatures
        player_x, player_y = player_ship.rect.center
        for sig_x, sig_y, color in signatures:
            # Relative to player
            rel_x = sig_x - player_x
            rel_y = sig_y - player_y

            # Scale to radar
            radar_px = center_x + rel_x * radar_scale
            radar_py = center_y + rel_y * radar_scale

            # Only draw if within radar bounds
            if radar_x < radar_px < radar_x + radar_size and radar_y < radar_py < radar_y + radar_size:
                pygame.draw.circle(self.screen, color, (int(radar_px), int(radar_py)), 4)

        # Draw label
        if not hasattr(self, 'font_tiny'):
            self.font_tiny = pygame.font.Font(None, 12)
        label = self.font_tiny.render("RADAR", True, (200, 150, 0))
        self.screen.blit(label, (radar_x + 5, radar_y - 20))

    def draw_missile_vectors(
            self, player_id, missiles, player_ship, camera_x, camera_y
    ):
        """Draw incoming missile trajectory vectors with correct screen-space alignment.

        Draws high-visibility vector lines anchored at screen edges.
        """
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # Viewport boundaries (constrained by UI panels)
        panel_width = 600
        thin_height = 200

        world_left = panel_width
        world_right = screen_width - panel_width
        world_top = thin_height
        world_bottom = screen_height - thin_height

        # Viewport center (reference origin for edge projection)
        center_x = (world_left + world_right) / 2
        center_y = (world_top + world_bottom) / 2

        enemy_missiles = [
            m
            for m in missiles
            if getattr(m, "contact", None) and m.contact.player_id == player_id
        ]

        for missile in enemy_missiles:
            # Convert missile position to screen space
            screen_x = missile.pos_x - camera_x
            screen_y = missile.pos_y - camera_y

            # Only draw edge indicators for off-screen threats
            if not (
                    world_left < screen_x < world_right
                    and world_top < screen_y < world_bottom
            ):

                # 1. Project Line of Sight to Viewport Edges
                # Calculates true direction vector from center of screen to off-screen missile
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

                # 2. Missile Velocity Vector Alignment
                # Note: Pygame's Y-axis is inverted (0 at top, increases downward).
                # If your game's world Y goes UP, flip vel_y below: dir_y = -missile.vel_y
                vel_mag = math.hypot(missile.vel_x, missile.vel_y)
                if vel_mag > 0:
                    dir_x = missile.vel_x / vel_mag
                    dir_y = missile.vel_y / vel_mag  # Change to -missile.vel_y if Y points up in world space
                else:
                    # Default pointing toward center if stationary
                    dir_x = -rel_x / math.hypot(rel_x, rel_y)
                    dir_y = -rel_y / math.hypot(rel_x, rel_y)

                # 3. Vector Line Properties (Longer & Prominent)
                vector_length = 75  # Increased from 30px for high visibility
                end_x = edge_x + dir_x * vector_length
                end_y = edge_y + dir_y * vector_length

                # High-visibility colors
                vector_color = (255, 140, 0)  # Bright CRT Orange
                lock_color = (255, 40, 40)  # Sharp Red Lock Bracket

                # Draw Main Trajectory Line (Thicker width=3 for CRT punch)
                pygame.draw.line(
                    self.screen,
                    vector_color,
                    (edge_x, edge_y),
                    (end_x, end_y),
                    3,
                )

                # Draw Vector Tip (Small crossbar to accent movement direction)
                perp_x = -dir_y * 4
                perp_y = dir_x * 4
                pygame.draw.line(
                    self.screen,
                    vector_color,
                    (end_x - perp_x, end_y - perp_y),
                    (end_x + perp_x, end_y + perp_y),
                    2,
                )

                # 4. Target Lock Bracket Box at Edge Anchor
                box_size = 12
                hx, hy = edge_x, edge_y

                # Corners
                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx - box_size, hy - box_size),
                    (hx - box_size + 5, hy - box_size),
                    2,
                )
                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx - box_size, hy - box_size),
                    (hx - box_size, hy - box_size + 5),
                    2,
                )

                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx + box_size, hy - box_size),
                    (hx + box_size - 5, hy - box_size),
                    2,
                )
                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx + box_size, hy - box_size),
                    (hx + box_size, hy - box_size + 5),
                    2,
                )

                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx - box_size, hy + box_size),
                    (hx - box_size + 5, hy + box_size),
                    2,
                )
                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx - box_size, hy + box_size),
                    (hx - box_size, hy + box_size - 5),
                    2,
                )

                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx + box_size, hy + box_size),
                    (hx + box_size - 5, hy + box_size),
                    2,
                )
                pygame.draw.line(
                    self.screen,
                    lock_color,
                    (hx + box_size, hy + box_size),
                    (hx + box_size, hy + box_size - 5),
                    2,
                )