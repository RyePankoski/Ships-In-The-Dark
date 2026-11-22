"""Clickable console buttons.

Buttons are immediate-mode: whoever draws a button registers it in the same
call, so the clickable area is always exactly what's on screen and can never
drift from the drawing. Each frame's buttons become the click targets for the
next frame (input is handled before drawing).

Every button names an *action*: the same string the keyboard produces for that
key (see MainScene.KEY_ACTIONS), so a click and a key press run the same code.
A `hold` button doesn't fire an action; while the mouse is held on it, it
reports its action as a held virtual key instead (e.g. 'arrow_key_left' to
sweep the laser).
"""
import pygame

from utility import theme
from asset_handlers import fonts


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

    def block_below(self):
        """A full-screen overlay was drawn: nothing registered before it can be clicked."""
        self._building = []

    # --- Input side -------------------------------------------------------
    def _top_at(self, pos):
        # Last drawn is on top
        for button in reversed(self.active):
            if button.rect.collidepoint(pos):
                return button
        return None

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
    """The one instrument-box style: a single plain border.

    Args:
        rect: Box to draw.
        color: Border colour.
        fill: Background colour, or None to leave what's underneath.
        tick: Unused. Kept so callers don't change.
        width: Border thickness.
    """
    rect = pygame.Rect(rect)
    if fill is not None:
        pygame.draw.rect(screen, fill, rect)
    pygame.draw.rect(screen, color, rect, width)


def draw_button(screen, rect, label, key=None, lit=None, enabled=True, font=None, key_font=None,
                lit_color=theme.GREEN, align="left"):
    """One console push-button in the game's frame style.

    Args:
        rect: Where to draw it.
        label: Main text.
        key: Keyboard shortcut shown small in the corner (e.g. "Q"), or None.
        lit: None for a plain button, else True/False for its status lamp.
        enabled: Greyed out and unclickable-looking when False.
        lit_color: Lamp colour when lit (green = system on, amber = caution).
        align: "left" (lamp + label) or "center".
    """
    rect = pygame.Rect(rect)
    font = font or fonts.font(17)
    key_font = key_font or fonts.font(12)

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
    pygame.draw.rect(screen, border, rect, 1)

    clip = screen.get_clip()
    screen.set_clip(rect.inflate(-2, -2))

    x = rect.left + 10
    if lit is not None:
        lamp_r = 4
        lamp_c = (x + lamp_r, rect.centery)
        pygame.draw.circle(screen, lit_color if (lit and enabled) else theme.AMBER_FAINT, lamp_c, lamp_r)
        if lit and enabled:
            pygame.draw.circle(screen, theme.WHITE, lamp_c, 1)
        x += lamp_r * 2 + 8

    # render_steady: buttons are controls, they shouldn't stutter like readouts
    text = font.render_steady(label, True, text_color)
    if align == "center" and lit is None:
        screen.blit(text, text.get_rect(center=rect.center))
    else:
        screen.blit(text, text.get_rect(midleft=(x, rect.centery)))

    if key:
        hint = key_font.render_steady(key, True, theme.AMBER_DIM)
        screen.blit(hint, hint.get_rect(bottomright=(rect.right - 5, rect.bottom - 2)))

    screen.set_clip(clip)
