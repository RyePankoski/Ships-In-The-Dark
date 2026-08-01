import pygame
import sys
from core import Core

pygame.init()
clock = pygame.time.Clock()
FPS = 25

screen = pygame.display.set_mode(pygame.display.get_desktop_sizes()[0])
core = Core(screen)


def main():
    running = True
    while running:
        events = pygame.event.get()
        dt = clock.tick(FPS) / 1000
        for event in events:
            if event.type == pygame.QUIT:
                return False

        core.run(dt)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
