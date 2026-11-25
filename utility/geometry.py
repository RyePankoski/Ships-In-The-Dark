import math


def squared_distance(start, end):
    dx = start[0] - end[0]
    dy = start[1] - end[1]
    return dx * dx + dy * dy


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


# Returns the ship-style heading (same convention as ship.heading, counter-clockwise) from origin to target.
# Returns 0 when origin and target are the same point.
def heading_to(origin, target):
    rel_x = target[0] - origin[0]
    rel_y = target[1] - origin[1]
    bearing = math.degrees(math.atan2(rel_x, -rel_y))
    return (-bearing) % 360


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
