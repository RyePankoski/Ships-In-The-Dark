"""The look of the game in one place: palette, font, and CRT post-processing settings.

Colour rules (one meaning per colour):
    AMBER  - the console itself: frames, labels, headings, inactive-but-present.
             Bright amber doubles as "caution" (recharging, tracking, hull getting low).
    GREEN  - live data: sensor returns, radar, scans, readouts, your laser.
    RED    - threats only: locks on you, damage, hostile fire, things that kill you.
    WHITE  - you: your own marker, hot cores of beams and blips, your FTL/blink effects.

If you want to reskin the game, change the values here and nothing else.
"""
import pygame

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BLACK = (0, 0, 0)
BG = (3, 8, 5)                  # panel fill
BG_SENSOR = (4, 10, 6)          # inside instrument screens

AMBER = (210, 150, 0)
AMBER_BRIGHT = (255, 200, 40)
AMBER_DIM = (90, 65, 0)
AMBER_FAINT = (45, 32, 0)

GREEN = (70, 235, 110)
GREEN_BRIGHT = (175, 255, 190)
GREEN_DIM = (30, 110, 55)
GREEN_FAINT = (10, 32, 16)

RED = (255, 60, 50)
RED_BRIGHT = (255, 120, 110)
RANGE_RING = (*GREEN, 55)  # the radar's distance rings while range bands are on
RANGE_BAND = (*RED_BRIGHT, 40)  # a radar distance band holding something that moves
RED_DIM = (120, 28, 22)

WHITE = (235, 240, 230)
GREY = (120, 120, 105)          # "nothing here" / idle text

# Starfield: inert background, so it takes the amber phosphor. Each star is this
# colour scaled by its brightness, which keeps stars from reading as live data.
STAR_TINT = (255, 200, 40)

# World-view things that aren't UI
ASTEROID = (185, 140, 70)        # rock outline
ASTEROID_FILL = (34, 25, 12)     # rock body

# Per-material rock colours: (outline, body). Rocky uses ASTEROID / ASTEROID_FILL above.
ASTEROID_METALLIC = ((160, 165, 170), (30, 32, 34))      # gray
ASTEROID_SEMI_METALLIC = ((200, 170, 125), (38, 31, 20))  # tan
ASTEROID_ICY = ((110, 170, 255), (14, 24, 42))           # blue

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
FONT_FILE = "VT323-Regular.ttf"
# VT323 draws smaller than most fonts at the same pixel size, so every requested
# size is multiplied by this. Raise it to make all text bigger, lower it to shrink.
FONT_SCALE = 1.3



# ---------------------------------------------------------------------------
# CRT post-processing (see asset_handlers/crt.py)
# ---------------------------------------------------------------------------
CRT_ENABLED = True
CRT_TOGGLE_KEY = pygame.K_F9

GLOW_STRENGTH = 110             # 0-255: how much of the blurred image is added back
GLOW_DOWNSCALE = 6              # bigger = wider, softer glow (and cheaper)

SCANLINE_SPACING = 3
SCANLINE_ALPHA = 70             # 0-255
VIGNETTE_ALPHA = 110            # darkness at the very corners

# Grunge (see asset_handlers/grime.py and crt.py). Set any number to 0 to turn that effect off.
GRIME_ENABLED = True            # stained, scratched, burnt-in panel textures
GRAIN_STRENGTH = 14             # 0-255: brightest speckle of the animated static
HUM_BAR_STRENGTH = 9            # 0-255: the slow bright band that rolls down the tube
HUM_BAR_SPEED = 0.06            # pixels per millisecond
TEAR_CHANCE = 0.02              # per frame: a strip of the picture jumps sideways
GLASS_DIRT = 1.0                # dust, smudges and scratches on the tube glass (0 = clean)
FLICKER_CHANCE = 0.005          # per frame: whole picture dims for a frame

# Phosphor persistence: things that move leave a fading afterglow behind them
RADAR_SWEEP_PERIOD_MS = 3200    # one full turn of the radar arm
BULLET_TRAIL_LENGTH = 14        # pixels of tracer trail behind a bullet
READOUT_SPEED = 0.5             # background terminals in the top panel: 1.0 = original pace, lower = slower
TEXT_FLICKER_INTERVAL = (4.0, 11.0)    # seconds between one label stuttering (0, 0 = never)
TEXT_FLICKER_DURATION_MS = (150, 450)  # how long the stutter lasts
