import pygame


class DrawUI:
    def __init__(self, screen):
        self.font_small = None
        self.screen = screen

        self.font = pygame.font.Font(None, 28)  # Was 18
        self.font_small = pygame.font.Font(None, 22)  # Was 16

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
