"""Clickable console buttons.

Buttons are immediate-mode: whoever draws a button registers it in the same
call, so the clickable area is always exactly what's on screen and can never
drift from the drawing. Each frame's buttons become the click targets for the
next frame (input is handled before drawing).

Every button names an *action*: MainScene.perform() has a branch per name that
calls the method. A key press calls that same method directly.
A `hold` button doesn't fire an action; while the mouse is held on it,
held_action() reports its name instead (e.g. 'arrow_key_left' to sweep the
laser).
"""
import pygame

from config import theme
from asset_handlers.ui_scale import px, ui_font


class Button:
    __slots__ = ("rect", "action", "enabled", "hold")

    def __init__(self, rect, action, enabled=True, hold=False):
        self.rect = pygame.Rect(rect)
        self.action = action
        self.enabled = enabled
        self.hold = hold


class ButtonLayer:
    def __init__(self):
        self._building = []   # registered while this frame draws
        self.active = []      # last finished frame: what clicks are tested against
        self.last_click_pos = None  # screen position of the latest click that hit a button

    # --- Drawing side -----------------------------------------------------
    def begin_frame(self):
        self._building = []

    def end_frame(self):
        self.active = self._building
        self._building = []

    def register(self, rect, action, enabled=True, hold=False):
        self._building.append(Button(rect, action, enabled, hold))

    def button(self, screen, rect, label, action, key=None, lit=None, enabled=True, hold=False, **style):
        """Draw a console button and register its click area in the same call."""
        draw_button(screen, rect, label, key=key, lit=lit, enabled=enabled, **style)
        self.register(rect, action, enabled=enabled, hold=hold)

    def button_row(self, screen, rect, specs, gap=8):
        rect = pygame.Rect(rect)
        gap = px(gap)
        total = sum(spec[0] for spec in specs)
        usable = rect.width - gap * (len(specs) - 1)
        x = rect.left
        for i, (weight, label, action, kwargs) in enumerate(specs):
            w = rect.right - x if i == len(specs) - 1 else int(usable * weight / total)
            self.button(screen, (x, rect.top, w, rect.height), label, action, **kwargs)
            x += w + gap

    def block_below(self):
        """A full-screen overlay was drawn: nothing registered before it can be clicked."""
        self._building = []

    # --- Input side -------------------------------------------------------
    def _top_at(self, pos):
        for button in reversed(self.active):
            if button.rect.collidepoint(pos):
                return button
        return None

    def is_over_button(self, pos):
        return self._top_at(pos) is not None

    def clicked_actions(self, events):
        """Actions of the enabled, non-hold buttons left-clicked in these events."""
        actions = []
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                button = self._top_at(event.pos)
                if button and button.enabled and not button.hold:
                    actions.append(button.action)
                    self.last_click_pos = event.pos
        return actions

    def held_action(self):
        """The action of the hold button under a held left mouse button, or None."""
        if not pygame.mouse.get_focused() or not pygame.mouse.get_pressed()[0]:
            return None
        button = self._top_at(pygame.mouse.get_pos())
        if button and button.enabled and button.hold:
            return button.action
        return None


def draw_frame(screen, rect, color=theme.AMBER, fill=theme.BG, tick=10, width=1):
    rect = pygame.Rect(rect)
    if fill is not None:
        pygame.draw.rect(screen, fill, rect)
    pygame.draw.rect(screen, color, rect, px(width))


_blank_lines_cache = None


def draw_blank_underlay(screen):
    global _blank_lines_cache
    w, h = screen.get_size()
    if _blank_lines_cache is None or _blank_lines_cache.get_size() != (w, h):
        _blank_lines_cache = pygame.Surface((w, h))
        _blank_lines_cache.fill((110, 110, 110))
        for y in range(0, h, 2):
            pygame.draw.line(_blank_lines_cache, theme.BLACK, (0, y), (w, y))
    screen.blit(_blank_lines_cache, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


def draw_button(screen, rect, label, key=None, lit=None, enabled=True, font=None, key_font=None,
                lit_color=theme.GREEN, align="left", states=("ON", "OFF"), sub=None, sub_font=None):
    """sub: a second, smaller line under the label saying what the button does."""
    rect = pygame.Rect(rect)
    font = font or ui_font(17)
    key_font = key_font or ui_font(12)
    sub_font = sub_font or ui_font(13)

    # No hover state: a physical switch doesn't react to a cursor floating over it,
    # only to being pushed in.
    mouse = pygame.mouse.get_pos() if pygame.mouse.get_focused() else (-1, -1)
    pressed = enabled and rect.collidepoint(mouse) and pygame.mouse.get_pressed()[0]

    if not enabled:
        border, text_color, fill = theme.AMBER_FAINT, theme.AMBER_DIM, theme.BG
    elif pressed:
        border, text_color, fill = theme.AMBER_BRIGHT, theme.AMBER_BRIGHT, theme.AMBER_FAINT
    else:
        border, text_color, fill = theme.AMBER_DIM, theme.AMBER, theme.BG

    pygame.draw.rect(screen, fill, rect)
    pygame.draw.rect(screen, border, rect, px(1))

    clip = screen.get_clip()
    screen.set_clip(rect.inflate(px(-2), px(-2)))

    x = rect.left + px(10)
    # With a description the label rides on the upper line and the description sits under it
    label_y = rect.centery
    sub_surf = None
    if sub:
        sub_surf = sub_font.render_steady(sub, True, theme.AMBER_DIM)
        gap = px(3)
        block = font.get_height() + gap + sub_surf.get_height()
        top = rect.centery - block // 2
        label_y = top + font.get_height() // 2
        screen.blit(sub_surf, sub_surf.get_rect(topleft=(rect.left + px(10), top + font.get_height() + gap)))

    if lit is not None:
        on = lit and enabled
        status = font.render_steady(f"[{states[0] if lit else states[1]}]", True,
                                    lit_color if on else theme.AMBER_DIM)
        screen.blit(status, status.get_rect(midleft=(x, label_y)))
        x += status.get_width() + px(8)

    # render_steady: buttons are controls, they shouldn't stutter like readouts
    text = font.render_steady(label, True, text_color)
    if align == "center" and lit is None and not sub:
        screen.blit(text, text.get_rect(center=rect.center))
    else:
        screen.blit(text, text.get_rect(midleft=(x, label_y)))

    if key:
        hint = key_font.render_steady(key, True, theme.AMBER_DIM)
        if sub:
            screen.blit(hint, hint.get_rect(topright=(rect.right - px(6), rect.top + px(4))))
        else:
            screen.blit(hint, hint.get_rect(bottomright=(rect.right - px(5), rect.bottom - px(2))))

    screen.set_clip(clip)
