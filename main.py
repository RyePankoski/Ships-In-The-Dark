import pygame
import sys
from core import Core

pygame.init()
clock = pygame.time.Clock()
FPS = 144
core = Core()


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
