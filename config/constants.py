# Units: distances in world units (pixels), speeds in units per second,
# accelerations in units per second squared, angles in degrees, times in seconds.


# ---------------------------------------------------------------------------
# Ship handling
# ---------------------------------------------------------------------------
SHIP_THRUST = 20  # acceleration along the nose while thrusting
SHIP_MAX_SPEED = 80
RETRO_THRUST_FRACTION = 0.5  # reverse burn (down key) as a fraction of forward thrust

SHIP_TURN_RATE = 150  # top turn rate, degrees per second
SHIP_TURN_ACCEL = 600  # how quickly the turn rate eases toward its target, degrees per second squared
SHIP_TURN_SLOWDOWN = 0.4  # fraction of turn rate lost at full speed, so fast ships arc wider

FLIGHT_ASSIST_DRAG = 0.4  # coasting bleed per second with the dampener on
DRIFT_DRAG = 0.0  # coasting bleed per second with the dampener off (0 = pure drift, no speed loss)
BRAKE_DRAG = 1.0  # per second while braking (tab)

# ---------------------------------------------------------------------------
# Ship fuel and health
# ---------------------------------------------------------------------------
SHIP_MAX_FUEL = 401
SHIP_MAX_HEALTH = 100
THROTTLED_SPEED = 40  # top speed while the hull is badly damaged
LOW_FUEL_FRACTION = 0.1  # low-fuel warning when the tank falls to this fraction of SHIP_MAX_FUEL
BLINK_FUEL_THRESHOLD = 50
HIGH_USE = 4


RADIATION_BUILDUP = 0.5
RADIATION_BLEED = 3.0

# ---------------------------------------------------------------------------
# Power draw
# ---------------------------------------------------------------------------
# Switches that change a ship's power draw. The owning player sets them; the server applies them.
POWER_FLAGS = ('laser_on', 'prox_scan_on', 'blinking', 'deep_field_on', 'dampening', 'material_assessor_on', 'radar_scan_on', 'dfs_detector_on', 'range_bands_on')

# Ship systems
THRUST_DRAW = 2
BRAKING_DRAW = 2
DAMPENING_DRAW = 0.75
TURNING_DRAW = 0.25
BLINKING_DRAW = 50

# Instruments and mining
LASER_DRAW = 1
DEEP_FIELD_DRAW = 0.75
PROXIMITY_SCAN_DRAW = 0.1
RADAR_SCAN_DRAW = 0.25
DFS_DETECTOR_DRAW = 0.05
RANGE_BANDS_DRAW = 0.8
MATERIAL_ASSESSOR_DRAW = 0.25
MINING_DRAW = 5

# ---------------------------------------------------------------------------
# Weapons: missiles
# ---------------------------------------------------------------------------
MISSILE_THRUST = 200
MISSILE_MAX_SPEED = 500
MISSILE_FUEL = 15
MISSILE_FUEL_USE_RATE = 3
TOTAL_MISSILES = 5

# Missile obstacle avoidance (single-feeler steering)
MISSILE_FEELER_LENGTH = 200  # how far ahead the missile looks for rocks
MISSILE_FEELER_STEP = 25  # sample spacing; keep < GRID_SIZE so no cell is skipped
MISSILE_AVOID_CLEARANCE = 250  # berth given to a rock; tune to visible missile size
MISSILE_AVOID_WEIGHT = 1.0  # 1.0 = up to ~45 deg deflection from straight-at-target
MISSILE_AVOID_SMOOTH = 0.15  # 0.1 = heavy smoothing (gliding), 0.4 = snappier

# ---------------------------------------------------------------------------
# Weapons: bullets
# ---------------------------------------------------------------------------
BULLET_SPEED = 600
BULLET_LIFETIME = 2
BULLET_DAMAGE = 2
BULLET_HIT_RADIUS = 25  # a pirate bullet hurts a ship it passes within this many pixels of its center

# ---------------------------------------------------------------------------
# Mining laser: locks the nearest mine able rock in range and burns it away
# ---------------------------------------------------------------------------
MINING_RANGE = 200  # center to center, world units
MINING_TIME = 8.0  # seconds of beam on one rock
MINING_FUEL_YIELD = 100  # fuel from an icy rock
MINING_MISSILE_YIELD = 1  # missiles from a metallic rock
# What each mine able material pays out. Anything not listed can't be mined.
MINING_YIELD = {'icy': 'fuel', 'metallic': 'missile', 'semi-metallic': 'hull'}

# ---------------------------------------------------------------------------
# Sensors and countermeasures
# ---------------------------------------------------------------------------
RADAR_PULSE_RANGE = 4000
RADAR_PULSE_SPEED = 2

CLOSE_RANGE_SCAN_RANGE = 1000

CORRIDOR_DEPTH = 8000  # deep field scan configuration
CORRIDOR_WIDTH = 2000

LASER_RANGE = 5000  # laser assessor
LASER_STEP = 2  # laser assessor sampling step

DECOY_LIFETIME = 30

# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------
# World size, rock count, drones and pirates are per match: see simulation/settings.py
GRID_SIZE = 500

# Asteroid radii are rolled between these when the world is generated
MIN_ROCK_RADIUS = 50
MAX_ROCK_RADIUS = 100

# Ids below this are player ships (1, 2, ...). Everything else the world creates
# gets an id from FIRST_OBJECT_ID upwards.
FIRST_OBJECT_ID = 1000

SINGLE_PLAYER_SPAWN = (500, 500)
SINGLE_PLAYER_ENEMY_SPAWN = (500, 600)

# ---------------------------------------------------------------------------
# Networking and timing
# ---------------------------------------------------------------------------
PORT = 27015
TICK_RATE = 20  # server simulation steps per second
TICK_DT = 1 / TICK_RATE
BROADCAST_RATE = 20  # server state snapshots sent per second (independent of the frame rate)
REF_HZ = 60  # the frame rate the per-step ship handling constants were tuned at
SHUTDOWN_WAIT = 2  # seconds the shutdown sequence runs before quitting (core/main_scene.py)

# Client-side prediction (see simulation/snapshot.py)
SNAPSHOT_AGE = 0.06  # how old a snapshot is on arrival: one tick plus a LAN trip, roughly
SNAP_DISTANCE = 400  # a gap bigger than this (blink, respawn) is a teleport, not an error to ease out
CORRECTION_RATE = 10  # per second; the smaller the gap after a snapshot, the sooner it's gone
LOCAL_VELOCITY_BLEND = 0.25  # how far our own ship's heading/speed is pulled to the server's per snapshot

# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------
CALLSIGN_MAX = 20

# The least visible your own ship can be to you (alpha 0-255). Enemies see the true visibility.
SELF_MIN_ALPHA = 25
CALLSIGN_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
