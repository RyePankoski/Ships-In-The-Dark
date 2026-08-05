import math
from utility.constants import *


class CloseRangeScan:
    def __init__(self, player_ship):
        self.player_ship = player_ship
        self.scan_range = CLOSE_RANGE_SCAN_RANGE
        self.confirmed_contacts = []  # [x, y, contact_type, (vx, vy), confidence, age, object_ref]

        self.confidence_decay = 0.999 # Per frame multiplier
        self.confirmation_time = 60  # Frames to reach full confidence (1.0)

    def update(self, spatial_contacts, list_contacts):
        """Always-on scan. Updates contacts and decays confidence over time.

        Args:
            spatial_contacts: Dict of grid-keyed dicts {'asteroids': {...}, 'drones': {...}, ...}
            list_contacts: Dict of flat lists {'ships': [...], 'decoys': [...], ...}
        """
        player_x, player_y = self.player_ship.rect.center

        # Build current detection set from what's in range
        current_detections = {}  # {object_ref: (x, y, vx, vy, type)}

        # Check list contacts (ships, decoys, etc.)
        self._scan_list_contacts(player_x, player_y, list_contacts, current_detections)

        # Check spatial contacts (asteroids, drones, etc.)
        self._scan_spatial_contacts(player_x, player_y, spatial_contacts, current_detections)

        # Add new detections
        for obj, (x, y, vx, vy, ctype) in current_detections.items():
            if not self._contact_exists(obj):
                self.confirmed_contacts.append([x, y, ctype, (vx, vy), 1.0, 0, obj])

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

    def _scan_list_contacts(self, player_x, player_y, list_contacts, current_detections):
        """Scan list-based contacts (ships, decoys, etc.) within range."""
        if not list_contacts:
            return

        for contact_type, contact_list in list_contacts.items():
            for contact in contact_list:
                if contact is self.player_ship:
                    continue

                # Get position
                if hasattr(contact, 'rect'):
                    c_x, c_y = contact.rect.center
                else:
                    c_x, c_y = contact.pos_x, contact.pos_y

                # Get velocity
                vx = getattr(contact, 'vel_x', 0)
                vy = getattr(contact, 'vel_y', 0)

                dist = math.hypot(c_x - player_x, c_y - player_y)
                if dist < self.scan_range:
                    # Type classification
                    if contact_type == 'ships':
                        ctype = 'SHIP'
                    elif contact_type == 'decoys':
                        ctype = 'DECOY'
                    else:
                        ctype = contact_type.rstrip('s').upper()

                    current_detections[contact] = (c_x, c_y, vx, vy, ctype)

    def _scan_spatial_contacts(self, player_x, player_y, spatial_contacts, current_detections):
        """Scan spatial contacts (grid-keyed) within range."""
        if not spatial_contacts:
            return

        for contact_type, contact_dict in spatial_contacts.items():
            for cell_list in contact_dict.values():
                for contact in cell_list:
                    c_x, c_y = contact.pos_x, contact.pos_y

                    # Get velocity (drones have dx/dy, asteroids have 0)
                    vx = getattr(contact, 'dx', 0)
                    vy = getattr(contact, 'dy', 0)

                    dist = math.hypot(c_x - player_x, c_y - player_y)
                    if dist < self.scan_range:
                        # Type classification
                        if contact_type == 'asteroids':
                            ctype = 'ASTEROID'
                        elif contact_type == 'drones':
                            ctype = 'DRONE'
                        else:
                            ctype = contact_type.rstrip('s').upper()

                        current_detections[contact] = (c_x, c_y, vx, vy, ctype)

    def _contact_exists(self, obj):
        """Check if object is already in confirmed list."""
        return any(c[6] is obj for c in self.confirmed_contacts)

    def get_contacts(self):
        """Return confirmed contacts formatted for display.

        Returns:
            List of (x, y, contact_type, (vx, vy), confidence) tuples
        """
        return [(c[0], c[1], c[2], c[3], c[4]) for c in self.confirmed_contacts]