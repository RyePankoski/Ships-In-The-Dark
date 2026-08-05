import math
import random
import time

import pygame
import sys
import os
from utility.constants import *
from pathlib import Path


def generate_stars(star_count=100000, world_width=100000, world_height=100000):
    """Generate random stars across the world"""
    import random
    stars = []
    for _ in range(star_count):
        x = random.randint(0, world_width)
        y = random.randint(0, world_height)
        brightness = random.randint(100, 255)
        size = random.randint(1, 3)
        stars.append((x, y, brightness, size))
    return stars


def is_visible_to_camera(obj, camera_x, camera_y, screen_width, screen_height):
    # Get object position
    if hasattr(obj, 'rect'):
        obj_x, obj_y = obj.rect.center
    else:
        obj_x, obj_y = obj.pos_x, obj.pos_y

    # Viewport bounds (must match draw_ui_layout panel dimensions)
    panel_width = 500
    thin_height = 100

    world_left = panel_width
    world_right = screen_width - panel_width
    world_top = thin_height
    world_bottom = screen_height - thin_height

    # Convert to screen space
    screen_x = obj_x - camera_x
    screen_y = obj_y - camera_y

    # Check if within viewport
    return (world_left < screen_x < world_right and
            world_top < screen_y < world_bottom)


class DrawGame:
    def __init__(self, screen):
        self.screen = screen
        if getattr(sys, "frozen", False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).resolve().parent.parent

        asset_path = base_path / "assets"
        self.player_ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship.png"))
        self.enemy_ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/enemy_ship.png"))
        self.missile_sprite = pygame.image.load(os.path.join(asset_path, "pngs/missile.png"))
        self.drone_sprite = pygame.image.load(os.path.join(asset_path, "pngs/drone.png"))
        self.drone_mining = pygame.image.load(os.path.join(asset_path, "pngs/drone_mining.png"))
        self.decoy_sprite = pygame.image.load(os.path.join(asset_path, "pngs/decoy.png"))
        self.pirate_ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/pirate.png"))
        self.pirate_ship_ambushing = pygame.image.load(os.path.join(asset_path, "pngs/pirate_ambushing.png"))
        self.player_ship_moving_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_moving.png"))

        # Generate starfield
        self.stars = generate_stars(10000, WORLD_WIDTH, WORLD_HEIGHT)

    def start_blit(self):
        self.screen.fill((0, 0, 0))

    def draw_stars(self, camera_x, camera_y):
        """Draw starfield with camera offset"""
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        for star_x, star_y, brightness, size in self.stars:
            screen_x = star_x - camera_x
            screen_y = star_y - camera_y

            # Only draw if on screen
            if -10 < screen_x < screen_width + 10 and -10 < screen_y < screen_height + 10:
                pygame.draw.circle(self.screen, (brightness, brightness, brightness), (screen_x, screen_y), size)

    def draw_asteroids(self, asteroids, camera_x, camera_y):
        for asteroid_list in asteroids.values():
            for asteroid in asteroid_list:

                if not is_visible_to_camera(asteroid, camera_x, camera_y, self.screen.get_width(), self.screen.get_height()):
                    continue

                screen_x = asteroid.pos_x - camera_x
                screen_y = asteroid.pos_y - camera_y
                pygame.draw.circle(
                    self.screen,
                    (150, 105, 40),
                    (screen_x, screen_y),
                    asteroid.size
                )

    def draw_explosions(self, explosions, camera_x, camera_y):
        for explosion in explosions:
            screen_x = explosion[0] - camera_x
            screen_y = explosion[1] - camera_y
            pygame.draw.circle(self.screen, (255, 255, 255), (screen_x, screen_y), 50)

    def draw_missiles(self, missiles, camera_x, camera_y):
        for missile in missiles:
            screen_x = missile.pos_x - camera_x
            screen_y = missile.pos_y - camera_y
            rotated_sprite = pygame.transform.rotate(self.missile_sprite, missile.heading)
            rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
            self.screen.blit(rotated_sprite, rotated_rect)

    def draw_drones(self, drones, camera_x, camera_y):
        for cell in drones.values():
            for drone in cell:
                if not is_visible_to_camera(drone, camera_x, camera_y, self.screen.get_width(), self.screen.get_height()):
                    continue
                screen_x = drone.pos_x - camera_x
                screen_y = drone.pos_y - camera_y

                if drone.am_mining:
                    self.screen.blit(self.drone_mining, (screen_x, screen_y))
                else:
                    self.screen.blit(self.drone_sprite, (screen_x, screen_y))

    def draw_decoys(self, decoys, camera_x, camera_y):
        for decoy in decoys:
            screen_x = decoy.pos_x - camera_x
            screen_y = decoy.pos_y - camera_y
            self.screen.blit(self.decoy_sprite, (screen_x, screen_y))

    def draw_ships(self, ships, camera_x, camera_y):
        for ship in ships:
            screen_x = ship.rect.center[0] - camera_x
            screen_y = ship.rect.center[1] - camera_y

            if ship.player:
                if ship.thrusting:
                    rotated_sprite = pygame.transform.rotate(self.player_ship_moving_sprite, ship.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)
                else:
                    rotated_sprite = pygame.transform.rotate(self.player_ship_sprite, ship.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)
            else:
                rotated_sprite = pygame.transform.rotate(self.enemy_ship_sprite, ship.heading)
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)

    def draw_pirates(self, pirates, camera_x, camera_y):
        for cell in pirates.values():
            for pirate in cell:
                screen_x = pirate.rect.center[0] - camera_x
                screen_y = pirate.rect.center[1] - camera_y

                if pirate.ambushing:
                    rotated_sprite = pygame.transform.rotate(self.pirate_ship_ambushing, pirate.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)
                else:
                    rotated_sprite = pygame.transform.rotate(self.pirate_ship_sprite, pirate.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)

    def draw_bullets(self, bullets, camera_x, camera_y):
        for bullet in bullets:
            screen_x = bullet.pos_x - camera_x
            screen_y = bullet.pos_y - camera_y
            pygame.draw.circle(self.screen, bullet.color, (screen_x, screen_y), 2)

    def draw_end_game(self, message="SIGNAL LOST", subtitle="SYNCHRONIZATION LOST. DEBUG:42*1a2"):
        w, h = self.screen.get_width(), self.screen.get_height()
        t = time.time()

        # Base phosphor colors
        PHOSPHOR = (0, 200, 50)
        PHOSPHOR_DIM = (0, 90, 60)
        PHOSPHOR_DARK = (0, 50, 25)

        if not hasattr(self, "_sig_font"):
            self._sig_font = pygame.font.Font(None, 130)
            self._sig_font_sub = pygame.font.Font(None, 40)
            self._diag_font = pygame.font.Font(None, 24)  # New font for diagnostics

        # 1. Dead feed: wash to the UI's own black-green.
        wash = pygame.Surface((w, h), pygame.SRCALPHA)
        wash.fill((2, 8, 2, 235))
        self.screen.blit(wash, (0, 0))

        # 2. Grid & Sonar Sweep (Drone Interface)
        # Faint tactical grid
        grid = pygame.Surface((w, h), pygame.SRCALPHA)
        grid_spacing = 60
        for x in range(0, w, grid_spacing):
            pygame.draw.line(grid, PHOSPHOR_DARK, (x, 0), (x, h), 1)
        for y in range(0, h, grid_spacing):
            pygame.draw.line(grid, PHOSPHOR_DARK, (0, y), (w, y), 1)

        # Center crosshair
        cx, cy = w // 2, h // 2
        pygame.draw.circle(grid, PHOSPHOR_DIM, (cx, cy), 150, 1)
        pygame.draw.line(grid, PHOSPHOR_DIM, (cx - 170, cy), (cx + 170, cy), 1)
        pygame.draw.line(grid, PHOSPHOR_DIM, (cx, cy - 170), (cx, cy + 170), 1)

        # Sweeping radar/sonar line looking for connection
        sweep_angle = t * 3  # Speed of rotation
        sx = cx + math.cos(sweep_angle) * w
        sy = cy + math.sin(sweep_angle) * w
        pygame.draw.line(grid, PHOSPHOR_DIM, (cx, cy), (sx, sy), 2)
        self.screen.blit(grid, (0, 0))

        # 3. Monochrome phosphor snow
        noise = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(160):
            nx = random.randint(0, w)
            ny = random.randint(0, h)
            v = random.randint(20, 70)
            pygame.draw.rect(noise, (0, v + 40, v, v), (nx, ny, 2, 2))
        self.screen.blit(noise, (0, 0))

        # 4. Gentle phosphor flicker
        flicker = 0.82 + 0.18 * math.sin(t * 14)

        # 5. Diagnostic overlay (Top Left)
        # Randomizing the hex code slightly based on time to look like it's churning
        err_code = hex(int(t * 100) % 0xFFFF)[2:].upper()
        diagnostics = [
            "UPLINK_NODE_04 ... FAIL",
            "TELEMETRY      ... NO CARRIER",
            "PNEUMATICS     ... OFFLINE",
            "SONAR_PING     ... TIMEOUT",
            f"SYS_ERR_LOG    ... 0x{err_code}"
        ]

        dy = 20
        for msg in diagnostics:
            diag_surf = self._diag_font.render(msg, True, PHOSPHOR_DIM)
            diag_surf.set_alpha(int(200 * flicker))
            self.screen.blit(diag_surf, (20, dy))
            dy += 22

        # 6. Title with soft monochrome bloom
        core = self._sig_font.render(message, True, PHOSPHOR)
        halo = self._sig_font.render(message, True, PHOSPHOR_DIM)
        core.set_alpha(int(255 * flicker))
        halo.set_alpha(int(150 * flicker))
        tw, th = core.get_width(), core.get_height()
        tx = w // 2 - tw // 2
        ty = h // 2 - th // 2 - 20

        # Draw halo slightly offset
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.screen.blit(halo, (tx + ox, ty + oy))
        self.screen.blit(core, (tx, ty))

        # 7. Subtitle with a blinking underscore cursor
        cursor = "_" if int(t * 2) % 2 == 0 else " "
        sub = self._sig_font_sub.render(f"> {subtitle} {cursor}", True, PHOSPHOR)
        sub.set_alpha(int(220 * flicker))
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, ty + th + 16))

        # 8. Reconnection attempt text (Bottom Left)
        attempt_num = int(t * 0.5) % 99
        dots = "." * (int(t * 3) % 4)
        reconnect_txt = f"AUTO-RECONNECT ATTEMPT {attempt_num:02d}/99{dots}"
        reconnect_surf = self._diag_font.render(reconnect_txt, True, PHOSPHOR)
        reconnect_surf.set_alpha(int(255 * flicker))
        self.screen.blit(reconnect_surf, (20, h - 30))

        # 9. One bright monochrome tear line sweeping slowly down the tube
        tear_y = int((t * 90) % h)
        tear = pygame.Surface((w, 3), pygame.SRCALPHA)
        tear.fill((0, 255, 160, 45))
        self.screen.blit(tear, (0, tear_y))

        # 10. Scanlines to seat it in the glass
        scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(scan, (0, 0, 0, 110), (0, y), (w, y), 2)
        self.screen.blit(scan, (0, 0))
