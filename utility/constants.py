# Ship handling (units per second and per second squared; angles in degrees)
SHIP_THRUST = 50  # acceleration along the nose while thrusting
SHIP_MAX_SPEED = 200
RETRO_THRUST_FRACTION = 0.5  # reverse burn (down key) as a fraction of forward thrust
SHIP_TURN_RATE = 150  # top turn rate, degrees per second
SHIP_TURN_ACCEL = 600  # how quickly the turn rate eases toward its target, degrees per second squared
SHIP_TURN_SLOWDOWN = 0.4  # fraction of turn rate lost at full speed, so fast ships arc wider
FLIGHT_ASSIST_DRAG = 0.9  # coasting bleed per second with the dampener on
DRIFT_DRAG = 0.08  # coasting bleed per second with the dampener off
BRAKE_DRAG = 3.0  # per second while braking (tab)
BOOST_THRUST_MULT = 2.0  # shift: thrust multiplier
BOOST_SPEED_MULT = 1.5  # shift: raises the speed cap

MISSILE_THRUST = 200  # was 0.4
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
TICK_RATE = 20  # server simulation steps per second
BROADCAST_RATE = 20  # server state snapshots sent per second (independent of the frame rate)

REF_HZ = 60 # the frame rate the per-step ship handling constants were tuned at
# Client-side prediction (see simulation/snapshot.py)
SNAPSHOT_AGE = 0.06  # how old a snapshot is on arrival: one tick plus a LAN trip, roughly
SNAP_DISTANCE = 400  # a gap bigger than this (blink, respawn) is a teleport, not an error to ease out
CORRECTION_RATE = 10  # per second; the smaller the gap after a snapshot, the sooner it's gone
LOCAL_VELOCITY_BLEND = 0.25  # how far our own ship's heading/speed is pulled to the server's per snapshot

