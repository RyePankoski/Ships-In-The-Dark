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
            screen_x = missile.rect.center[0] - camera_x
            screen_y = missile.rect.center[1] - camera_y
            rotated_sprite = pygame.transform.rotate(self.missile_sprite, missile.heading)
            rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
            self.screen.blit(rotated_sprite, rotated_rect)

    def draw_drones(self, drones, camera_x, camera_y):
        for cell in drones.values():
            for drone in cell:
                screen_x = drone.pos_x - camera_x
                screen_y = drone.pos_y - camera_y

                if drone.am_mining:
                    self.screen.blit(self.drone_mining, (screen_x, screen_y))
                else:
                    self.screen.blit(self.drone_sprite, (screen_x, screen_y))

    def draw_ships(self, ships, camera_x, camera_y):
        for ship in ships:
            screen_x = ship.rect.center[0] - camera_x
            screen_y = ship.rect.center[1] - camera_y

            if ship.player:
                rotated_sprite = pygame.transform.rotate(self.player_ship_sprite, ship.heading)
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)
            else:
                rotated_sprite = pygame.transform.rotate(self.enemy_ship_sprite, ship.heading)
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)

    def draw_signal_lost(self, message="SIGNAL LOST", subtitle="CARRIER LOST -- NO SYNC"):
        """Full-screen 'signal lost' game-over overlay, monochrome-phosphor CRT.

        Call every frame while the match is over: it self-animates (phosphor
        flicker, blinking cursor, a slow sweeping tear) off the wall clock, and
        draws its own scanlines, so it stands alone over the frozen world.
        """
        w, h = self.screen.get_width(), self.screen.get_height()
        t = time.time()

        # Single phosphor colour + its dim halo. Swap PHOSPHOR to amber
        # (255, 176, 0) for an amber-tube look; everything else follows it.
        PHOSPHOR = (0, 200, 50)
        PHOSPHOR_DIM = (0, 90, 60)

        if not hasattr(self, "_sig_font"):
            self._sig_font = pygame.font.Font(None, 130)
            self._sig_font_sub = pygame.font.Font(None, 40)

        # 1. Dead feed: wash to the UI's own black-green.
        wash = pygame.Surface((w, h), pygame.SRCALPHA)
        wash.fill((2, 8, 2, 235))
        self.screen.blit(wash, (0, 0))

        # 2. Monochrome phosphor snow -- single colour, faint. Re-rolled each
        #    frame so it shimmers like a dead channel.
        noise = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(160):
            nx = random.randint(0, w)
            ny = random.randint(0, h)
            v = random.randint(20, 70)
            pygame.draw.rect(noise, (0, v + 40, v, v), (nx, ny, 2, 2))
        self.screen.blit(noise, (0, 0))

        # 3. Gentle phosphor flicker -- no hard digital dropout.
        flicker = 0.82 + 0.18 * math.sin(t * 14)

        # 4. Title with a soft monochrome bloom: the same colour stamped a few
        #    px out as a dim halo (phosphor spread), NOT an RGB split.
        core = self._sig_font.render(message, True, PHOSPHOR)
        halo = self._sig_font.render(message, True, PHOSPHOR_DIM)
        core.set_alpha(int(255 * flicker))
        halo.set_alpha(int(150 * flicker))
        tw, th = core.get_width(), core.get_height()
        cx = w // 2 - tw // 2
        cy = h // 2 - th // 2 - 20
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.screen.blit(halo, (cx + ox, cy + oy))
        self.screen.blit(core, (cx, cy))

        # 5. Subtitle as a terminal line with a blinking underscore cursor.
        cursor = "_" if int(t * 2) % 2 == 0 else " "
        sub = self._sig_font_sub.render(f"> {subtitle} {cursor}", True, PHOSPHOR)
        sub.set_alpha(int(220 * flicker))
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, cy + th + 16))

        # 6. One bright monochrome tear line sweeping slowly down the tube.
        tear_y = int((t * 90) % h)
        tear = pygame.Surface((w, 3), pygame.SRCALPHA)
        tear.fill((0, 255, 160, 45))
        self.screen.blit(tear, (0, tear_y))

        # 7. Scanlines to seat it in the glass.
        scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(scan, (0, 0, 0, 110), (0, y), (w, y), 2)
        self.screen.blit(scan, (0, 0))
