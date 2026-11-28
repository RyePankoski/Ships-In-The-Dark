"""Tuning numbers and colour roles for asset_handlers/draw_ui.py.

Panel geometry shared with the instruments lives in config/ui_constants.py.
Pixel and font sizes are design pixels (see asset_handlers/ui_scale.py).
"""
from config import theme

# Font sizes: the operator console uses legacy_font, the menus use font
FONT_SIZE_BODY = 28
FONT_SIZE_RADAR = 25
FONT_SIZE_SCAN_HEADER = 32
FONT_SIZE_SCAN_BODY = 24
FONT_SIZE_GRID = 18
FONT_SIZE_TINY = 20
MENU_TITLE_SIZE = 56
MENU_FONT_SIZE = 28
MENU_SMALL_SIZE = 18
MENU_KEY_SIZE = 14

# Colour roles: what each colour means on the console
BORDER = theme.AMBER            # primary frame colour
SCOPE_GRID = theme.AMBER_FAINT  # world grid lines
SCOPE_GRID_TEXT = theme.AMBER_DIM
HUD_AMBER = theme.AMBER
DATA = theme.GREEN
LASER_ACTIVE = theme.GREEN     # your beam is a sensor
LASER_PAINTED = theme.AMBER_BRIGHT  # ...that has something on it
CAUTION_RED = (200, 30, 30)    # radar hatching past the world edge

# The large scope panels (deep field scan, tactical map, replay map)
SCOPE_BG = theme.BG_SENSOR
SCOPE_BORDER = theme.AMBER
SCOPE_HEADER = theme.AMBER_BRIGHT
SCOPE_DATA = theme.GREEN
SCOPE_ONLINE = theme.GREEN
SCOPE_OFFLINE = theme.GREY
SCOPE_THREAT = theme.RED
SCOPE_ORANGE = theme.AMBER_DIM  # the deep field scan's sweep lines

# Layout: plain pages (text screens, debrief, replay) and framed full-screen menus
PLAIN_MARGIN = 40
PLAIN_TOP = 32
MENU_MARGIN = 16
MENU_PAD = 28
MENU_GAP = 22
BOX_HEAD = 8  # room a box's heading line takes above its contents
IDENT_LINE = "ERGOT SYSTEMS // INTERSTELLAR COMPUTING DIVISION"
REV_LINE = "REV 4.7.2  BUILD 2026.11.21"

# Blink timing: frames per half-cycle for the flashes driven by lock_blink_counter
LOCK_BLINK_FREQUENCY = 10
LOCK_BORDER_WIDTH = 10
RADIATION_YELLOW = (255, 230, 0)
RADIATION_BLINK_FREQUENCY = 15
LASER_PAINTED_BLINK_FREQUENCY = 8
CATASTROPHE_STROBE_FREQUENCY = 12

# Hull hits: (seconds the picture takes to settle back, strength at the hit)
IMPACT_ASTEROID = (0.7, 0.5)
IMPACT_MISSILE = (3.5, 0.9)

# Ship vectors: heading line length is fixed, velocity line grows with speed (px)
HEADING_LEN = 110
SPEED_LEN = 150

# Tactical map: half-width of the view in world units
TACTICAL_MAP_RANGE = 5000
MARKER_SHAPES = ("CIRCLE", "SQUARE", "TRIANGLE", "DIAMOND", "CROSS")
REPLAY_PILOT_COLORS = (theme.GREEN, theme.AMBER_BRIGHT, theme.RED_BRIGHT, theme.WHITE, theme.GREEN_BRIGHT)

# Deep field scan headings: (compass point, degrees)
DFS_HEADINGS = (("N", 0), ("NE", 45), ("E", 90), ("SE", 135),
                ("S", 180), ("SW", 225), ("W", 270), ("NW", 315))

# Training splash
TUTORIAL_SPLASH_SECONDS = 4.0
TUTORIAL_SPLASH_ORBIT_SCALE = 1.35  # size of the ship's lap relative to the ring
TUTORIAL_SPLASH_BAR_LENGTH = 27     # '#' characters in a full loading bar

# Boot splash timing: when the log starts, the gap between lines, and typing speed
BOOT_START = 1.1
BOOT_LINE_DELAY = 0.48
BOOT_CHARS_PER_SECOND = 42
BOOT_PROMPT_AFTER = 4.2  # seconds before "PRESS ENTER TO CONTINUE" starts blinking
