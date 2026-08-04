import math
from utility.constants import *


class CloseRangeScan:
    def __init__(self, player_ship):
        self.player_ship = player_ship
        self.scan_range = CLOSE_RANGE_SCAN_RANGE
        self.confirmed_contacts = []  # (pos_x, pos_y, contact_type, velocity, confidence, age, object_ref)

        self.confidence_decay = 0.98  # Per frame multiplier
        self.confirmation_time = 60  # Frames to reach full confidence (1.0)

    def update(self, ships, asteroids, drones):
        """Always-on scan. Updates contacts and decays confidence over time."""
        player_x, player_y = self.player_ship.rect.center

        # Build current detection set from what's in range
        current_detections = {}  # {object_ref: (x, y, vx, vy, type)}

        for ship in ships:
            if ship is self.player_ship:
                continue
            dist = math.hypot(ship.pos_x - player_x, ship.pos_y - player_y)
            if dist < self.scan_range:
                current_detections[ship] = (ship.pos_x, ship.pos_y, ship.vel_x, ship.vel_y, "SHIP")

        for cell in asteroids.values():
            for asteroid in cell:
                dist = math.hypot(asteroid.pos_x - player_x, asteroid.pos_y - player_y)
                if dist < self.scan_range:
                    current_detections[asteroid] = (asteroid.pos_x, asteroid.pos_y, 0, 0, "ASTEROID")

        for cell in drones.values():
            for drone in cell:
                dist = math.hypot(drone.pos_x - player_x, drone.pos_y - player_y)
                if dist < self.scan_range:
                    current_detections[drone] = (drone.pos_x, drone.pos_y, drone.dx, drone.dy, "DRONE")

        # Add new detections

        for obj, (x, y, vx, vy, ctype) in current_detections.items():
            if not self._contact_exists(obj):
                self.confirmed_contacts.append([x, y, ctype, (vx, vy), 1.0, 0, obj])  # Start at 1.0 (100%)

        print(f"Confirmed contacts: {len(self.confirmed_contacts)}")

        # Update existing contacts
        updated_contacts = []
        for contact in self.confirmed_contacts:
            x, y, ctype, vel, confidence, age, obj = contact

            if obj in current_detections:
                # In range: update position and boost confidence
                new_x, new_y, vx, vy, _ = current_detections[obj]
                contact[0], contact[1] = new_x, new_y
                contact[3] = (vx, vy)
                contact[5] += 1  # Increment age

                # Confidence ramps up to 1.0 over confirmation_time frames
                if confidence < 1.0:
                    contact[4] = min(1.0, confidence + (1.0 / self.confirmation_time))
            else:
                # Out of range: decay confidence
                contact[4] *= self.confidence_decay
                contact[5] += 1  # Still increment age

            # Keep contacts above confidence threshold
            if contact[4] > 0.05:
                updated_contacts.append(contact)

        self.confirmed_contacts = updated_contacts

    def _contact_exists(self, obj):
        """Check if object is already in confirmed list."""
        return any(c[6] is obj for c in self.confirmed_contacts)

    def get_contacts(self):
        """Return confirmed contacts formatted for map display."""
        return [(c[0], c[1], c[2], c[3], c[4]) for c in self.confirmed_contacts]
