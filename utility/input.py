import pygame


def key_pressed(events, *keys):
    return any(event.type == pygame.KEYDOWN and event.key in keys for event in events)
