SHIP_THRUST = 100  # was 1

ANGLE_CHANGE_SPEED = 3  # was 0.4
SHIP_MAX_SPEED = 200
DAMPENING_FORCE = 0.9999
SHIP_BRAKE_FORCE = 0.99

MISSILE_THRUST = 50  # was 0.4
MISSILE_MAX_SPEED = 500  # was 10
MISSILE_FUEL = 15  # stays
MISSILE_FUEL_USE_RATE = 3  # stays (or adjust)

MISSILE_LIFETIME = 60
TOTAL_MISSILES = 3

# Missile obstacle avoidance (single-feeler steering)
MISSILE_FEELER_LENGTH = 200  # how far ahead the missile looks for rocks
MISSILE_FEELER_STEP = 25  # sample spacing; keep < GRID_SIZE so no cell is skipped
MISSILE_AVOID_CLEARANCE = 250  # berth given to a rock; tune to visible missile size
MISSILE_AVOID_WEIGHT = 1.0  # 1.0 = up to ~45 deg deflection from straight-at-target
MISSILE_AVOID_SMOOTH = 0.15  # 0.1 = heavy smoothing (gliding), 0.4 = snappier

WORLD_WIDTH = 10000
WORLD_HEIGHT = 10000
GRID_SIZE = 500

# Radar configuration
RADAR_PULSE_RANGE = 4000
RADAR_PULSE_SPEED = 2

# Laser configuration
LASER_STEP = 2
LASER_RANGE = 5000

# Deep field scan configuration
CORRIDOR_DEPTH = 8000
CORRIDOR_WIDTH = 2000

# Close range scanner
CLOSE_RANGE_SCAN_RANGE = 1000

# Decoy
DECOY_LIFETIME = 30

# Bullets
BULLET_SPEED = 600
BULLET_LIFETIME = 2

PORT = 27015
