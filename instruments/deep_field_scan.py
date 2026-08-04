import math
from utility.constants import *
from utility.util import distance, in_quadrant





class DeepFieldScan:
    def __init__(self, player_ship):
        self.player_ship = player_ship
        self.direction_index = 0  # 0-7 representing 0°, 45°, 90°, etc.
        self.directions = [0, 45, 90, 135, 180, 225, 270, 315]
        self.corridor_width = CORRIDOR_WIDTH
        self.corridor_depth = CORRIDOR_DEPTH

    def change_direction(self, inputs):
        """Handle input for direction changes (like laser)."""
        if inputs.get('arrow_key_down'):
            self.direction_index = (self.direction_index - 1) % 8
        if inputs.get('arrow_key_up'):
            self.direction_index = (self.direction_index + 1) % 8

    def run_scan(self, ships, asteroids, drones):
        """Scan quadrant and return contacts with object references."""
        contacts = []
        direction_deg = self.directions[self.direction_index]
        player_x, player_y = self.player_ship.rect.center

        # Check ships
        for ship in ships:
            if ship is self.player_ship:
                continue
            if in_quadrant(player_x, player_y, direction_deg, ship.rect.center):
                range_px = distance(player_x, player_y, ship.rect.center)
                is_moving = ship.total_velocity > 0.1
                ship.dfs_scanned = True
                contacts.append((range_px, 'ship', is_moving, 0.8, ship))

        # Check asteroids
        for cell in asteroids.values():
            for asteroid in cell:
                if in_quadrant(player_x, player_y, direction_deg, (asteroid.pos_x, asteroid.pos_y)):
                    range_px = distance(player_x, player_y, (asteroid.pos_x, asteroid.pos_y))
                    contacts.append((range_px, 'asteroid', False, 0.7, asteroid))

        # Check drones
        for cell in drones.values():
            for drone in cell:
                if in_quadrant(player_x, player_y, direction_deg, (drone.pos_x, drone.pos_y)):
                    range_px = distance(player_x, player_y, (drone.pos_x, drone.pos_y))
                    is_moving = drone.velocity > 0.1
                    contacts.append((range_px, 'unknown', is_moving, 0.6, drone))

        return sorted(contacts, key=lambda x: x[0])

