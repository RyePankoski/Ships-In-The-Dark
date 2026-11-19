import argparse
import sys

import pygame
from core.core import Core
from asset_handlers.crt import crt
from utility import theme

parser = argparse.ArgumentParser(description="Ships In The Dark")
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--single", action="store_true", help="skip the menu, start single-player")
mode.add_argument("--host", action="store_true", help="skip the menu, host a game")
mode.add_argument("--join", metavar="IP", help="skip the menu, join the game at IP")
parser.add_argument("--windowed", action="store_true", help="1280x720 window, handy for two copies on one PC")
args = parser.parse_args()

launch = {}
if args.single:
    launch = {'mode': 'single'}
elif args.host:
    launch = {'mode': 'host'}
elif args.join:
    launch = {'mode': 'join', 'ip': args.join}

pygame.init()
clock = pygame.time.Clock()
FPS = 20

size = (1280, 720) if args.windowed else pygame.display.get_desktop_sizes()[0]
screen = pygame.display.set_mode(size)
core = Core(screen, launch)

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
