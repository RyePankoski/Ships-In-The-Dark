import pygame


def collect_inputs():
    keys = pygame.key.get_pressed()

    inputs = {
        'left': keys[pygame.K_a],
        'right': keys[pygame.K_d],
        'up': keys[pygame.K_w],
        'down': keys[pygame.K_s],
        'space': keys[pygame.K_SPACE],
        'p': keys[pygame.K_p],
        'm': keys[pygame.K_m],
        'j': keys[pygame.K_j],
        'h': keys[pygame.K_h],
        'shift': keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT],
        'g': keys[pygame.K_g],
        'x': keys[pygame.K_x],
    }

    return inputs


def end_blit():
    pygame.display.flip()
