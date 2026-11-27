import math

from config.constants import MAX_ROCK_RADIUS, SHIP_CENTRE_OFFSET


def squared_distance(start, end):
    dx = start[0] - end[0]
    dy = start[1] - end[1]
    return dx * dx + dy * dy


# True if no asteroid in the grid is close enough to (x, y) to count as occupied.
# A rock's centre can be up to its radius plus the clearance away, and that can
# reach into the neighbouring cells, so the grid lookup includes those too.
def is_empty_space(asteroids, x, y):
    for asteroid in asteroids.near(x, y, reach=asteroids.reach_for(MAX_ROCK_RADIUS + 50)):
        if squared_distance((x, y), (asteroid.pos_x, asteroid.pos_y)) < (asteroid.size + 50) ** 2:
            return False
    return True


# True if a ship placed with its top-left at (x, y) would have a clear centre. The ship's
# collision centre is SHIP_CENTRE_OFFSET from its top-left corner.
def is_clear_ship_spot(asteroids, x, y):
    return is_empty_space(asteroids, x + SHIP_CENTRE_OFFSET, y + SHIP_CENTRE_OFFSET)


def in_sector(origin_x, origin_y, direction_deg, target_pos, half_width_deg=45):
    """True if target lies strictly within half_width_deg of a compass bearing (0 = north/up, 90 = east)."""
    rel_x = target_pos[0] - origin_x
    rel_y = target_pos[1] - origin_y
    if rel_x == 0 and rel_y == 0:
        return False
    bearing = math.degrees(math.atan2(rel_x, -rel_y))
    offset = (bearing - direction_deg + 180) % 360 - 180
    return abs(offset) < half_width_deg


# Ship headings (objects/ship.py facing()) run counter-clockwise, compass bearings run clockwise,
# so the heading is negated before asking in_sector.
def in_front(origin_x, origin_y, heading_deg, target_pos, half_width_deg=45):
    return in_sector(origin_x, origin_y, -heading_deg, target_pos, half_width_deg)


# True if a ray from origin along the ship-style heading, lookahead units long, passes within radius of center.
def ray_hits_circle(origin, heading_deg, lookahead, center, radius):
    rad = math.radians(heading_deg)
    forward_x, forward_y = -math.sin(rad), -math.cos(rad)
    rel_x = center[0] - origin[0]
    rel_y = center[1] - origin[1]
    along = rel_x * forward_x + rel_y * forward_y
    if along < 0 or along > lookahead:
        return False
    across = abs(rel_x * forward_y - rel_y * forward_x)
    return across < radius


# Returns the ship-style heading (same convention as ship.heading, counter-clockwise) from origin to target.
# Returns 0 when origin and target are the same point.
def heading_to(origin, target):
    rel_x = target[0] - origin[0]
    rel_y = target[1] - origin[1]
    bearing = math.degrees(math.atan2(rel_x, -rel_y))
    return (-bearing) % 360


# Returns "up", "down", "left" or "right" for where target sits relative to origin on screen (up is north, y grows downward).
# Uses whichever axis the target is further along, so a diagonal target counts as vertical when |dy| >= |dx|.
# Returns None when origin and target are the same point.
def cardinal_direction(origin, target):
    rel_x = target[0] - origin[0]
    rel_y = target[1] - origin[1]
    if rel_x == 0 and rel_y == 0:
        return None
    if abs(rel_y) >= abs(rel_x):
        return "up" if rel_y < 0 else "down"
    return "left" if rel_x < 0 else "right"


# Returns "left" or "right" depending on which side of the ship-style heading ray from origin the target lies.
# Target exactly on the heading line counts as "right".
def which_side(origin, heading_deg, target_pos):
    left_x, left_y = _left_unit_vector(heading_deg)
    rel_x = target_pos[0] - origin[0]
    rel_y = target_pos[1] - origin[1]
    if rel_x * left_x + rel_y * left_y > 0:
        return "left"
    return "right"


# Moves point by amount units to the left or right of the ship-style heading and returns the new point.
# side must be "left" or "right".
def shift_point(point, heading_deg, amount, side):
    left_x, left_y = _left_unit_vector(heading_deg)
    if side == "left":
        signed_amount = amount
    elif side == "right":
        signed_amount = -amount
    else:
        raise ValueError(f"side must be 'left' or 'right', got {side!r}")
    return (point[0] + left_x * signed_amount, point[1] + left_y * signed_amount)


# Unit vector pointing to the left of a ship-style heading (heading 0 faces up/north, left is west).
def _left_unit_vector(heading_deg):
    rad = math.radians(heading_deg)
    return (-math.cos(rad), math.sin(rad))


def map_to_range_linear(value, in_min, in_max, out_min, out_max):
    t = (value - in_min) / (in_max - in_min)  # 0.0 .. 1.0 across the input range
    t = max(0.0, min(1.0, t))  # clamp the fraction, not the output
    return out_min + t * (out_max - out_min)


def map_to_range_log(value, in_min, in_max, out_min, out_max, steepness=1.0):
    # Lower steepness means a steeper slope initially.
    # steepness must not be 0 (use map_to_range_linear for a straight line).
    value = max(value, in_min)
    return map_to_range_linear(math.log(value + steepness), math.log(in_min + steepness), math.log(in_max + steepness), out_min, out_max)


def map_to_range_exp(value, in_min, in_max, out_min, out_max, steepness=1.0):
    # Higher steepness means the output stays low longer, then rises sharply near in_max.
    # steepness must not be 0 (use map_to_range_linear for a straight line).
    t = map_to_range_linear(value, in_min, in_max, 0.0, 1.0)  # 0.0 .. 1.0, clamped
    curved = (math.exp(steepness * t) - 1) / (math.exp(steepness) - 1)  # 0.0 .. 1.0, curved
    return map_to_range_linear(curved, 0.0, 1.0, out_min, out_max)
