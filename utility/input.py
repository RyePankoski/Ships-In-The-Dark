import pygame


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
        'esc': keys[pygame.K_ESCAPE],

        # Modifiers
        'left_shift': keys[pygame.K_LSHIFT],
        'right_shift': keys[pygame.K_RSHIFT],
        'ctrl': keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL],
        'left_alt': keys[pygame.K_LALT],
        'right_alt': keys[pygame.K_RALT],
        'slash': keys[pygame.K_SLASH],

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
        'n': keys[pygame.K_n],
        'v' : keys[pygame.K_v],

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


def key_pressed(events, *keys):
    """True if any of `keys` went down this frame. Use for one-shot actions; held keys
    (collect_inputs) are for continuous movement and firing."""
    return any(event.type == pygame.KEYDOWN and event.key in keys for event in events)
