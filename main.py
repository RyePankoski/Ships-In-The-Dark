import sys

import pygame
from core.root import Core
from asset_handlers.crt import crt
from config import theme
from config.constants import REF_HZ


def shutdown():
    pygame.quit()
    sys.exit()


def main():
    pygame.init()
    clock = pygame.time.Clock()

    size = pygame.display.get_desktop_sizes()[0]
    # size = 1920, 1080
    screen = pygame.display.set_mode(size)
    core = Core(screen)

    while True:
        events = pygame.event.get()
        dt = clock.tick(REF_HZ) / 1000
        for event in events:
            if event.type == pygame.QUIT:
                shutdown()
            if event.type == pygame.KEYDOWN and event.key == theme.CRT_TOGGLE_KEY:
                crt.toggle()
        core.run(dt, events)
        if core.exit_requested:
            shutdown()


if __name__ == "__main__":
    main()
