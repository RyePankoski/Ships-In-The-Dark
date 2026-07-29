import pygame
import sys
import os


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

    def start_blit(self):
        self.screen.fill((0, 0, 0))

    def draw_explosions(self, explosions):
        for explosion in explosions:
            pygame.draw.circle(self.screen, (255, 255, 255), explosion, 50)

    def draw_missiles(self, missiles):
        for missile in missiles:
            rotated_sprite = pygame.transform.rotate(self.missile_sprite, missile.heading)
            rotated_rect = rotated_sprite.get_rect(center=missile.rect.center)
            self.screen.blit(rotated_sprite, rotated_rect)

    def draw_ships(self, ships):
        for ship in ships:
            if ship.player:
                rotated_sprite = pygame.transform.rotate(self.player_ship_sprite, ship.heading)
                rotated_rect = rotated_sprite.get_rect(center=ship.rect.center)
                self.screen.blit(rotated_sprite, rotated_rect)
            else:
                rotated_sprite = pygame.transform.rotate(self.enemy_ship_sprite, ship.heading)
                rotated_rect = rotated_sprite.get_rect(center=ship.rect.center)
                self.screen.blit(rotated_sprite, rotated_rect)