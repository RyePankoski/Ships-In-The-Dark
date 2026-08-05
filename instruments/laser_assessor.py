import math

from objects.asteroid import Asteroid
from objects.drone import Drone
from objects.pirate import Pirate
from objects.ship import Ship
from utility.constants import *


def _set_painted(contact, value):
    """Set painted flag on a contact (handles different attribute names)."""
    if hasattr(contact, 'painted'):
        contact.painted = value
    if hasattr(contact, 'is_painted'):
        contact.is_painted = value


class LaserAssessor:
    def __init__(self, player_ship):
        self.painted = False
        self.direction = 0
        self.ship_of_origin = player_ship

        self.signature_position = (0, 0)
        self.previous_signature_position = (0, 0)

        self.current_target = None
        self.previous_target = None
        self.laser_locked = False
        self.tracking_lost = False

        self.moving_laser = False

    def shine_laser(self, spatial_contacts, list_contacts):
        if self.laser_locked:
            self.lock_laser()

        target_type = "NOTHING"

        # Clear all painted flags
        self._clear_all_painted(spatial_contacts, list_contacts)

        rad = math.radians(self.direction)
        dx, dy = math.cos(rad), math.sin(rad)

        ray_x, ray_y = self.ship_of_origin.rect.center[0], self.ship_of_origin.rect.center[1]
        travelled = 0.0

        while (0 < ray_x < WORLD_WIDTH and 0 < ray_y < WORLD_HEIGHT
               and travelled < LASER_RANGE):
            travelled += LASER_STEP
            ray_x += dx * LASER_STEP
            ray_y += dy * LASER_STEP

            # Check list contacts (ships, decoys, missiles, etc.)
            hit = self._check_list_contacts_laser(ray_x, ray_y, list_contacts)
            if hit:
                contact, x, y, target_type = hit
                _set_painted(contact, True)
                self.current_target = contact
                return (ray_x, ray_y), target_type

            ray_sector = (int(ray_x // GRID_SIZE), int(ray_y // GRID_SIZE))
            hit = self._check_spatial_contacts_laser(ray_x, ray_y, ray_sector, spatial_contacts)
            if hit:
                contact, x, y, target_type = hit
                _set_painted(contact, True)
                self.current_target = contact
                return (ray_x, ray_y), target_type

        return (ray_x, ray_y), target_type

    def lock_laser(self):
        if self.current_target is None or not self.laser_locked:
            return

        # All contacts use pos_x/pos_y

        if isinstance(self.current_target, Ship):
            target_x, target_y = self.current_target.rect.center
        else:
            target_x = self.current_target.pos_x
            target_y = self.current_target.pos_y

        origin_x, origin_y = self.ship_of_origin.rect.center[0], self.ship_of_origin.rect.center[1]

        angle = math.atan2(target_y - origin_y, target_x - origin_x)
        self.direction = (math.degrees(angle) + 360) % 360

    def assess_target(self, x, y, contact):
        self.previous_signature_position = self.signature_position
        self.signature_position = (x, y)

        self.previous_target = self.current_target
        self.current_target = contact

        if self.laser_locked and self.previous_target != self.current_target:
            self.laser_locked = False
            self.tracking_lost = True

        if self.previous_signature_position == self.signature_position:
            return "ASTEROID / STATIC"
        else:
            return "VESSEL / MOVING"

    def _clear_all_painted(self, spatial_contacts, list_contacts):
        """Clear painted flag on all contacts."""
        # Spatial contacts
        if spatial_contacts:
            for contact_dict in spatial_contacts.values():
                for cell_list in contact_dict.values():
                    for contact in cell_list:
                        _set_painted(contact, False)

        # List contacts
        if list_contacts:
            for contact_list in list_contacts.values():
                for contact in contact_list:
                    if contact is not self.ship_of_origin:
                        _set_painted(contact, False)

    def _check_list_contacts_laser(self, ray_x, ray_y, list_contacts):
        """Check list contacts against ray. Returns (contact, x, y, type) or None."""
        if not list_contacts:
            return None

        for contact_type, contacts in list_contacts.items():
            for contact in contacts:
                if contact is self.ship_of_origin:
                    continue

                if isinstance(contact, Ship):
                    c_x = contact.rect.center[0]
                    c_y = contact.rect.center[1]
                else:
                    c_x = contact.pos_x
                    c_y = contact.pos_y

                dist_sq = (c_x - ray_x) ** 2 + (c_y - ray_y) ** 2
                hit_radius = getattr(contact, 'radar_cross_section', 50)

                if dist_sq < hit_radius ** 2:
                    target_type = self.assess_target(c_x, c_y, contact)
                    return contact, c_x, c_y, target_type

        return None

    def _check_spatial_contacts_laser(self, ray_x, ray_y, ray_sector, spatial_contacts):
        if not spatial_contacts:
            return None

        for contact_type, contact_dict in spatial_contacts.items():
            if ray_sector not in contact_dict:
                continue

            for contact in contact_dict[ray_sector]:

                dist_sq = (contact.pos_x - ray_x) ** 2 + (contact.pos_y - ray_y) ** 2
                hit_radius = getattr(contact, 'radar_cross_section',
                                     getattr(contact, 'size', 50))

                if dist_sq < hit_radius ** 2:
                    target_type = self.assess_target(contact.pos_x, contact.pos_y, contact)
                    return contact, contact.pos_x, contact.pos_y, target_type

        return None  # After all contact types checked

    def change_direction(self, inputs, dt):
        if inputs['arrow_key_left']:
            self.direction -= 40 * dt
            self.laser_locked = False
        if inputs['arrow_key_right']:
            self.direction += 40 * dt
            self.laser_locked = False
        # self.direction %= 360

    def set_direction(self, direction):
        self.direction = direction
