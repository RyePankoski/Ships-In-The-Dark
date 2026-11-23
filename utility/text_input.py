import pygame


def blink_cursor():
    return "_" if pygame.time.get_ticks() // 500 % 2 == 0 else " "


def edit_text(events, text, allowed, max_len, on_type=None):
    """Apply this frame's typing to `text`: backspace, plus characters `allowed` accepts.
    `on_type` is called (no args) for each accepted keystroke."""
    for event in events:
        if event.type != pygame.KEYDOWN:
            continue
        if event.key == pygame.K_BACKSPACE:
            text = text[:-1]
            if on_type:
                on_type()
        elif event.unicode and allowed(event.unicode) and len(text) < max_len:
            text += event.unicode
            if on_type:
                on_type()

    return text
