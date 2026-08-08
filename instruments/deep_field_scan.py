import math
from utility.constants import *
from utility.util import in_quadrant, dfs_sqrt_distance


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

    def run_scan(self, spatial_contacts, list_contacts):
        contacts = []
        direction_deg = self.directions[self.direction_index]
        player_x, player_y = self.player_ship.rect.center

        # Check list contacts (ships, decoys, etc.)
        self._check_list_contacts(
            player_x, player_y, direction_deg, list_contacts, contacts
        )

        # Check spatial contacts (asteroids, drones, etc.)
        self._check_spatial_contacts(
            player_x, player_y, direction_deg, spatial_contacts, contacts
        )

        return sorted(contacts, key=lambda x: x[0])

    def _check_list_contacts(self, player_x, player_y, direction_deg, list_contacts, contacts):
        """Check all list-based contacts (ships, decoys, etc.) in corridor."""
        if not list_contacts:
            return

        for contact_type, contact_list in list_contacts.items():
            for contact in contact_list:
                if contact is self.player_ship:
                    continue

                # Get contact position
                if hasattr(contact, 'rect'):
                    c_x, c_y = contact.rect.center
                else:
                    c_x, c_y = contact.pos_x, contact.pos_y

                if in_quadrant(player_x, player_y, direction_deg, (c_x, c_y)):
                    range_px = dfs_sqrt_distance(player_x, player_y, (c_x, c_y))
                    is_moving = getattr(contact, 'total_velocity', 0) > 0.1

                    # Type classification
                    if contact_type == 'ships':
                        contact_class = 'ship'
                        confidence = 0.8
                    elif contact_type == 'decoys':
                        contact_class = 'decoy'
                        confidence = 0.6
                    else:
                        contact_class = contact_type.rstrip('s')  # plurals -> singular
                        confidence = 0.7

                    contacts.append((range_px, contact_class, is_moving, confidence, contact))

    def _check_spatial_contacts(self, player_x, player_y, direction_deg, spatial_contacts, contacts):
        """Check all spatial contacts (grid-keyed) in corridor."""
        if not spatial_contacts:
            return

        for contact_type, contact_dict in spatial_contacts.items():
            for cell_list in contact_dict.values():
                for contact in cell_list:
                    c_x, c_y = contact.pos_x, contact.pos_y

                    if in_quadrant(player_x, player_y, direction_deg, (c_x, c_y)):
                        range_px = dfs_sqrt_distance(player_x, player_y, (c_x, c_y))
                        is_moving = getattr(contact, 'velocity', 0) > 0.1

                        # Type classification
                        if contact_type == 'asteroids':
                            contact_class = 'asteroid'
                            confidence = 0.7
                        elif contact_type == 'drones':
                            contact_class = 'unknown'
                            confidence = 0.6
                        else:
                            contact_class = contact_type.rstrip('s')
                            confidence = 0.65

                        contacts.append((range_px, contact_class, is_moving, confidence, contact))