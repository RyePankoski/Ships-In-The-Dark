import argparse
import sys

import pygame
from core.root import Core
from asset_handlers.crt import crt
from utility import theme
from utility.constants import REF_HZ

parser = argparse.ArgumentParser(description="Ships In The Dark")
args = parser.parse_args()

pygame.init()
clock = pygame.time.Clock()
FPS = REF_HZ

size = pygame.display.get_desktop_sizes()[0]
screen = pygame.display.set_mode(size)
core = Core(screen)


def main():
    while True:
        events = pygame.event.get()
        dt = clock.tick(FPS) / 1000
        for event in events:
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == theme.CRT_TOGGLE_KEY:
                crt.toggle()
        core.run(dt, events)


if __name__ == "__main__":
    main()
