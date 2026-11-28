# The UI is laid out in design pixels (a DESIGN_WIDTH x DESIGN_HEIGHT window) and
# converted to real pixels here, according to the size of the window.
import pygame

from asset_handlers import fonts
from config import ui_constants as ui


def ui_scale():
    width, height = pygame.display.get_surface().get_size()
    # The tighter axis wins, so the layout always fits whatever the aspect ratio
    return min(width / ui.DESIGN_WIDTH, height / ui.DESIGN_HEIGHT)


# A length in design pixels, as real pixels. Anything non-zero stays at least one
# pixel, because pygame reads a line width of 0 as "fill the shape".
def px(value):
    if value == 0:
        return 0
    scaled = round(value * ui_scale())
    if scaled == 0:
        return 1 if value > 0 else -1
    return scaled


def ui_font(size):
    return fonts.font(size * ui_scale())


def ui_legacy_font(size):
    return fonts.legacy_font(size * ui_scale())
