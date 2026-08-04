import math
from utility.constants import (
    WORLD_WIDTH, WORLD_HEIGHT, GRID_SIZE,
    RADAR_PULSE_RANGE, RADAR_PULSE_SPEED,
)
from utility.precomputed_angles import RADAR_DIRECTIONS

RED = (255, 0, 0)
WHITE = (255, 255, 255)


class RadarSystem:
    def __init__(self):
        self.scanning = False
        self.current_frame = 1
        self.scan_frames = 100
        self.current_ray = 0
        self.scan_resolution = 360
        self.rays_per_frame = None
        self.radar_rays = None

        self.passed_ship = None
        self.spatial_contacts = None  # Dict of dicts: {'asteroids': {...}, 'drones': {...}}
        self.list_contacts = None  # Dict of lists: {'ships': [...], 'decoys': [...]}

    def begin_scan(self, passed_ship, spatial_contacts, list_contacts):
        """Start a radar scan.

        Args:
            passed_ship: The scanning ship
            spatial_contacts: Dict of grid-keyed dicts {'asteroids': {...}, 'drones': {...}, ...}
            list_contacts: Dict of flat lists {'ships': [...], 'decoys': [...], ...}
        """
        self.scanning = True
        self.current_frame = 1
        self.current_ray = 0
        self.passed_ship = passed_ship
        self.spatial_contacts = spatial_contacts
        self.list_contacts = list_contacts

        self.scan_frames = min(100, self.scan_resolution)
        self.radar_rays = RADAR_DIRECTIONS[self.scan_resolution]
        self.rays_per_frame = self.scan_resolution // self.scan_frames

    def continue_scan(self):
        """Continue an ongoing scan. Returns list of signatures found this frame."""
        signatures = []

        if self.current_frame >= self.scan_frames:
            self.scanning = False
            target_ray = self.scan_resolution
        else:
            completion_ratio = self.current_frame / self.scan_frames
            target_ray = int(completion_ratio * self.scan_resolution)

        origin_x, origin_y = self.passed_ship.rect.center

        while self.current_ray < target_ray:
            dx, dy = self.radar_rays[self.current_ray]
            self.current_ray += 1

            ray_distance = 0
            ray_x, ray_y = origin_x, origin_y
            hit_found = False

            while (0 < ray_x < WORLD_WIDTH and 0 < ray_y < WORLD_HEIGHT
                   and ray_distance < RADAR_PULSE_RANGE and not hit_found):
                ray_distance += RADAR_PULSE_SPEED
                ray_x += dx * RADAR_PULSE_SPEED
                ray_y += dy * RADAR_PULSE_SPEED
                ray_sector = (int(ray_x // GRID_SIZE), int(ray_y // GRID_SIZE))

                # Check list contacts (ships, decoys, etc.)
                hit_found = self._check_list_contacts(
                    ray_x, ray_y, origin_x, origin_y, signatures
                )
                if hit_found:
                    break

                hit_found = self._check_spatial_contacts(
                    ray_x, ray_y, ray_sector, signatures
                )
                if hit_found:
                    break

        self.current_frame += 1
        return signatures

    def _check_list_contacts(self, ray_x, ray_y, origin_x, origin_y, signatures):
        """Check all list-based contacts (ships, decoys, etc.) against the ray.

        Returns True if a hit was found.
        """
        if not self.list_contacts:
            return False

        for contact_type, contacts in self.list_contacts.items():
            for contact in contacts:
                if contact is self.passed_ship:
                    continue

                # Get contact position
                if hasattr(contact, 'rect'):
                    c_x, c_y = contact.rect.center
                else:
                    c_x, c_y = contact.pos_x, contact.pos_y

                # Check hit
                dist_sq = (c_x - ray_x) ** 2 + (c_y - ray_y) ** 2

                # Determine hit radius
                hit_radius = getattr(contact, 'radar_cross_section', 50)

                if dist_sq < hit_radius ** 2:
                    # Record ping angle
                    angle = math.atan2(origin_y - c_y, origin_x - c_x)
                    if hasattr(contact, 'enemy_radar_ping_coordinates'):
                        contact.enemy_radar_ping_coordinates.append(angle)

                    # Determine color
                    painted = getattr(contact, 'painted', False)
                    color = RED if painted else WHITE

                    signatures.append((ray_x, ray_y, color))
                    return True

        return False

    def _check_spatial_contacts(self, ray_x, ray_y, ray_sector, signatures):
        if not self.spatial_contacts:
            return False

        for contact_type, contact_dict in self.spatial_contacts.items():
            if ray_sector not in contact_dict:
                continue

            for contact in contact_dict[ray_sector]:
                dist_sq = (contact.pos_x - ray_x) ** 2 + (contact.pos_y - ray_y) ** 2

                # Determine hit radius
                hit_radius = getattr(contact, 'radar_cross_section',
                                     getattr(contact, 'size', 50))

                if dist_sq < hit_radius ** 2:
                    painted = getattr(contact, 'painted', False) or getattr(contact, 'is_painted', False)
                    color = RED if painted else WHITE

                    signatures.append((ray_x, ray_y, color))
                    return True

        return False