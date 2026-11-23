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
