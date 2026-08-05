import pygame
from utility.constants import *
import math


def collect_inputs():
    keys = pygame.key.get_pressed()

    inputs = {
        # Movement
        'left': keys[pygame.K_a],
        'right': keys[pygame.K_d],
        'up': keys[pygame.K_w],
        'down': keys[pygame.K_s],
        'arrow_key_left': keys[pygame.K_LEFT],
        'arrow_key_right': keys[pygame.K_RIGHT],
        'arrow_key_up': keys[pygame.K_UP],
        'arrow_key_down': keys[pygame.K_DOWN],

        # Common actions
        'space': keys[pygame.K_SPACE],
        'enter': keys[pygame.K_RETURN],
        'escape': keys[pygame.K_ESCAPE],
        'tab': keys[pygame.K_TAB],

        # Modifiers
        'left_shift': keys[pygame.K_LSHIFT] ,
        'right_shift': keys[pygame.K_RSHIFT],
        'ctrl': keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL],
        'left_alt': keys[pygame.K_LALT],
        'right_alt': keys[pygame.K_RALT],

        # Letters (your existing ones + common game keys)
        'q': keys[pygame.K_q],
        'e': keys[pygame.K_e],
        'r': keys[pygame.K_r],
        'g': keys[pygame.K_g],
        'h': keys[pygame.K_h],
        'i': keys[pygame.K_i],
        'j': keys[pygame.K_j],
        'k': keys[pygame.K_k],
        'l': keys[pygame.K_l],
        'm': keys[pygame.K_m],
        'o': keys[pygame.K_o],
        'p': keys[pygame.K_p],
        'x': keys[pygame.K_x],
        'c': keys[pygame.K_c],
        'f': keys[pygame.K_f],
        'z': keys[pygame.K_z],
        't': keys[pygame.K_t],

        # Numbers
        '1': keys[pygame.K_1],
        '2': keys[pygame.K_2],
        '3': keys[pygame.K_3],
        '4': keys[pygame.K_4],
        '5': keys[pygame.K_5],
        '6': keys[pygame.K_6],
        '7': keys[pygame.K_7],
        '8': keys[pygame.K_8],
        '9': keys[pygame.K_9],
        '0': keys[pygame.K_0],
    }

    return inputs

def in_quadrant(origin_x, origin_y, direction_deg, target_pos):

    target_x, target_y = target_pos
    rel_x = target_x - origin_x
    rel_y = target_y - origin_y

    if direction_deg == 0:  # North
        return rel_y < 0
    elif direction_deg == 45:  # NE
        return rel_x > 0 > rel_y
    elif direction_deg == 90:  # East
        return rel_x > 0
    elif direction_deg == 135:  # SE
        return rel_x > 0 and rel_y > 0
    elif direction_deg == 180:  # South
        return rel_y > 0
    elif direction_deg == 225:  # SW
        return rel_x < 0 < rel_y
    elif direction_deg == 270:  # West
        return rel_x < 0
    elif direction_deg == 315:  # NW
        return rel_x < 0 and rel_y < 0

    return False


def distance(x1, y1, pos):
    """Euclidean distance."""
    dx = pos[0] - x1
    dy = pos[1] - y1
    return math.sqrt(dx ** 2 + dy ** 2)


def end_blit():
    pygame.display.flip()
