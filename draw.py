import pygame
import sys
import os
from constants import *


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


class Draw:
    def __init__(self):
        self.screen = pygame.display.set_mode(pygame.display.get_desktop_sizes()[0])

        # Handle PyInstaller bundled assets
        if getattr(sys, 'frozen', False):
            asset_path = os.path.join(sys._MEIPASS, 'assets')
        else:
            asset_path = 'assets'

        self.player_ship_sprite = pygame.image.load(os.path.join(asset_path, "ship.png"))
        self.enemy_ship_sprite = pygame.image.load(os.path.join(asset_path, "enemy_ship.png"))
        self.missile_sprite = pygame.image.load(os.path.join(asset_path, "missile.png"))

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
