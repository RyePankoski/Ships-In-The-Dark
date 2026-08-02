import math
from utility.constants import (
    WORLD_WIDTH, WORLD_HEIGHT, GRID_SIZE,
    RADAR_PULSE_RANGE, RADAR_PULSE_SPEED,
)
from utility.precomputed_angles import RADAR_DIRECTIONS  # you'll need to build this — see below

RED = (255, 0, 0)
WHITE = (255, 255, 255)


class RadarSystem:
    def __init__(self):
        self.scanning = False
        self.current_frame = 1
        self.scan_frames = 100
        self.current_ray = 0
        self.scan_resolution = 72
        self.rays_per_frame = None
        self.radar_rays = None

        self.passed_ship = None
        self.all_ships = None
        self.all_asteroids = None

    def begin_scan(self, passed_ship, all_ships, all_asteroids):
        self.scanning = True
        self.current_frame = 1
        self.current_ray = 0
        self.passed_ship = passed_ship
        self.all_ships = all_ships
        self.all_asteroids = all_asteroids

        self.scan_resolution = passed_ship.radar_resolution
        # Can't have < 1 ray per frame
        self.scan_frames = min(100, self.scan_resolution)
        self.radar_rays = RADAR_DIRECTIONS[self.scan_resolution]
        self.rays_per_frame = self.scan_resolution // self.scan_frames

    def continue_scan(self):
        signatures = []

        target_ray = self.rays_per_frame * self.current_frame
        if self.current_frame >= self.scan_frames:
            self.scanning = False
            target_ray = self.scan_resolution

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

                for ship in self.all_ships:
                    if ship is self.passed_ship:
                        continue
                    s_x, s_y = ship.rect.center
                    dist_sq = (s_x - ray_x) ** 2 + (s_y - ray_y) ** 2
                    if dist_sq < ship.radar_cross_section ** 2:
                        angle = math.atan2(origin_y - s_y, origin_x - s_x)
                        ship.enemy_radar_ping_coordinates.append(angle)

                        if ship.painted:
                            signatures.append((ray_x, ray_y, RED))
                        else:
                            signatures.append((ray_x, ray_y, WHITE))

                        hit_found = True
                        break

                if hit_found:
                    break

                # Then asteroids in this sector
                if ray_sector in self.all_asteroids:
                    for asteroid in self.all_asteroids[ray_sector]:
                        dist_sq = (asteroid.pos_x - ray_x) ** 2 + (asteroid.pos_y - ray_y) ** 2
                        if dist_sq < asteroid.size ** 2:
                            if asteroid.painted:
                                signatures.append((ray_x, ray_y, RED))
                            else:
                                signatures.append((ray_x, ray_y, WHITE))

                            hit_found = True
                            break

        self.current_frame += 1
        return signatures
