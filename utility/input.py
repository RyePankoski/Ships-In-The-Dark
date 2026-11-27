import pygame


def key_pressed(events, *keys):
    return any(event.type == pygame.KEYDOWN and event.key in keys for event in events)


def key_held(*keys):
    pressed = pygame.key.get_pressed()
    return any(pressed[key] for key in keys)


def held_movement():
    return {'up': key_held(pygame.K_w), 'down': key_held(pygame.K_s),
            'left': key_held(pygame.K_a), 'right': key_held(pygame.K_d),
            'left_shift': key_held(pygame.K_LSHIFT), 'tab': key_held(pygame.K_TAB)}
