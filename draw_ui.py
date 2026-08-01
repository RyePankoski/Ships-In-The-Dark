import math
import time

import pygame


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

    def draw_scanlines(self):
        """Draw CRT scanlines with transparency"""
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

        grid_size = 500  # World units between grid lines
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

    def draw_missile_vectors(
            self, player_id, missiles, player_ship, camera_x, camera_y
    ):
        """Draw incoming missile threat indicators and vectors along the screen edges.

        Designed for retro CRT aesthetic.
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

        # Center of screen for relative directional calculations
        screen_center_x = (world_left + world_right) / 2
        screen_center_y = (world_top + world_bottom) / 2

        # Filter incoming threat missiles targeting player
        enemy_missiles = [
            m
            for m in missiles
            if getattr(m, "contact", None) and m.contact.player_id == player_id
        ]

        current_time = time.time()

        for missile in enemy_missiles:
            # Convert missile world position to screen space
            screen_x = missile.pos_x - camera_x
            screen_y = missile.pos_y - camera_y

            # Only draw edge indicators for off-screen threats
            if not (
                    world_left < screen_x < world_right
                    and world_top < screen_y < world_bottom
            ):

                # Calculate distance to player ship for threat level
                dx = missile.pos_x - player_ship.pos_x
                dy = missile.pos_y - player_ship.pos_y
                dist = math.hypot(dx, dy)

                # 1. Dynamic Threat Level Color Coding
                if dist < 400:
                    color = (255, 30, 30)  # High Threat: Critical Red
                    pulse_speed = 15.0
                elif dist < 1000:
                    color = (255, 140, 0)  # Medium Threat: Warning Orange
                    pulse_speed = 8.0
                else:
                    color = (255, 220, 0)  # Low Threat: Yellow
                    pulse_speed = 3.0

                # 2. CRT Flicker/Pulse Effect
                # Blinks indicator intensity fast when close, slow when far
                flicker = math.sin(current_time * pulse_speed)
                if flicker < -0.3:
                    continue  # Skip drawing frame for a radar "tick" sweep look

                # 3. Raycast Direction to Edge (Center -> Off-screen position)
                rel_x = screen_x - screen_center_x
                rel_y = screen_y - screen_center_y
                angle = math.atan2(rel_y, rel_x)

                # Clamp vector to HUD edge bounds
                edge_x = max(
                    world_left + 10, min(world_right - 10, screen_x)
                )  # Default fallback
                edge_y = max(world_top + 10, min(world_bottom - 10, screen_y))

                # Ray-box intersection for accurate edge placement relative to player
                if rel_x != 0 and rel_y != 0:
                    scale_x = (
                        (world_right - screen_center_x - 10) / rel_x
                        if rel_x > 0
                        else (world_left - screen_center_x + 10) / rel_x
                    )
                    scale_y = (
                        (world_bottom - screen_center_y - 10) / rel_y
                        if rel_y > 0
                        else (world_top - screen_center_y + 10) / rel_y
                    )
                    scale = min(scale_x, scale_y)
                    edge_x = screen_center_x + rel_x * scale
                    edge_y = screen_center_y + rel_y * scale

                # 4. Missile Velocity Vector Projection
                vel_mag = math.hypot(missile.vel_x, missile.vel_y)
                if vel_mag > 0:
                    dir_x = missile.vel_x / vel_mag
                    dir_y = missile.vel_y / vel_mag
                else:
                    dir_x, dir_y = math.cos(angle), math.sin(angle)

                # Vector tail (length scales slightly with missile speed)
                vec_length = max(20, min(45, vel_mag * 2))
                end_x = edge_x + dir_x * vec_length
                end_y = edge_y + dir_y * vec_length

                # 5. Render CRT Visual Elements
                # Trajectory vector line
                pygame.draw.line(
                    self.screen, color, (edge_x, edge_y), (end_x, end_y), 2
                )

                # Main threat node
                pygame.draw.circle(
                    self.screen, color, (int(edge_x), int(edge_y)), 4, 1
                )
                pygame.draw.circle(
                    self.screen, color, (int(edge_x), int(edge_y)), 2
                )

                # Directional "chevron" tick on edge point pointing toward threat
                chev_angle1 = angle + math.pi * 0.85
                chev_angle2 = angle - math.pi * 0.85
                c1_x = edge_x + math.cos(chev_angle1) * 8
                c1_y = edge_y + math.sin(chev_angle1) * 8
                c2_x = edge_x + math.cos(chev_angle2) * 8
                c2_y = edge_y + math.sin(chev_angle2) * 8

                pygame.draw.line(
                    self.screen, color, (edge_x, edge_y), (c1_x, c1_y), 1
                )
                pygame.draw.line(
                    self.screen, color, (edge_x, edge_y), (c2_x, c2_y), 1
                )