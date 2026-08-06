import math
import random
import time

import pygame
import sys
import os
from utility.constants import *
from pathlib import Path


def generate_stars(star_count=100000, world_width=100000, world_height=100000):
    """Generate random stars across the world"""
    import random
    stars = []
    for _ in range(star_count):
        x = random.randint(0, world_width)
        y = random.randint(0, world_height)
        brightness = random.randint(100, 255)
        size = random.randint(1, 3)
        stars.append((x, y, brightness, size))
    return stars


def is_visible_to_camera(obj, camera_x, camera_y, screen_width, screen_height):
    # Get object position
    if hasattr(obj, 'rect'):
        obj_x, obj_y = obj.rect.center
    else:
        obj_x, obj_y = obj.pos_x, obj.pos_y

    # Viewport bounds (must match draw_ui_layout panel dimensions)
    panel_width = 500
    thin_height = 100

    world_left = panel_width
    world_right = screen_width - panel_width
    world_top = thin_height
    world_bottom = screen_height - thin_height

    # Convert to screen space
    screen_x = obj_x - camera_x
    screen_y = obj_y - camera_y

    # Check if within viewport
    return (world_left < screen_x < world_right and
            world_top < screen_y < world_bottom)


class DrawGame:
    def __init__(self, screen):
        self.screen = screen
        if getattr(sys, "frozen", False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).resolve().parent.parent

        asset_path = base_path / "assets"
        self.player_ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship.png"))
        self.enemy_ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/enemy_ship.png"))
        self.missile_sprite = pygame.image.load(os.path.join(asset_path, "pngs/missile.png"))
        self.drone_sprite = pygame.image.load(os.path.join(asset_path, "pngs/drone.png"))
        self.drone_mining = pygame.image.load(os.path.join(asset_path, "pngs/drone_mining.png"))
        self.decoy_sprite = pygame.image.load(os.path.join(asset_path, "pngs/decoy.png"))
        self.pirate_ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/pirate.png"))
        self.pirate_ship_ambushing = pygame.image.load(os.path.join(asset_path, "pngs/pirate_ambushing.png"))
        self.player_ship_moving_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_moving.png"))

        # Generate starfield
        self.stars = generate_stars(10000, WORLD_WIDTH, WORLD_HEIGHT)

    def start_blit(self):
        self.screen.fill((0, 0, 0))

    def draw_stars(self, camera_x, camera_y):
        """Draw starfield with camera offset"""
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        for star_x, star_y, brightness, size in self.stars:
            screen_x = star_x - camera_x
            screen_y = star_y - camera_y

            # Only draw if on screen
            if -10 < screen_x < screen_width + 10 and -10 < screen_y < screen_height + 10:
                pygame.draw.circle(self.screen, (brightness, brightness, brightness), (screen_x, screen_y), size)

    def draw_asteroids(self, asteroids, camera_x, camera_y):
        for asteroid_list in asteroids.values():
            for asteroid in asteroid_list:

                if not is_visible_to_camera(asteroid, camera_x, camera_y, self.screen.get_width(), self.screen.get_height()):
                    continue

                screen_x = asteroid.pos_x - camera_x
                screen_y = asteroid.pos_y - camera_y
                pygame.draw.circle(
                    self.screen,
                    (150, 105, 40),
                    (screen_x, screen_y),
                    asteroid.size
                )

    def draw_explosions(self, explosions, camera_x, camera_y):
        for explosion in explosions:
            screen_x = explosion[0] - camera_x
            screen_y = explosion[1] - camera_y
            pygame.draw.circle(self.screen, (255, 255, 255), (screen_x, screen_y), 50)

    def draw_missiles(self, missiles, camera_x, camera_y):
        for missile in missiles:
            screen_x = missile.pos_x - camera_x
            screen_y = missile.pos_y - camera_y
            rotated_sprite = pygame.transform.rotate(self.missile_sprite, missile.heading)
            rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
            self.screen.blit(rotated_sprite, rotated_rect)

    def draw_drones(self, drones, camera_x, camera_y):
        for cell in drones.values():
            for drone in cell:
                if not is_visible_to_camera(drone, camera_x, camera_y, self.screen.get_width(), self.screen.get_height()):
                    continue
                screen_x = drone.pos_x - camera_x
                screen_y = drone.pos_y - camera_y

                if drone.am_mining:
                    self.screen.blit(self.drone_mining, (screen_x, screen_y))
                else:
                    self.screen.blit(self.drone_sprite, (screen_x, screen_y))

    def draw_decoys(self, decoys, camera_x, camera_y):
        for decoy in decoys:
            screen_x = decoy.pos_x - camera_x
            screen_y = decoy.pos_y - camera_y
            self.screen.blit(self.decoy_sprite, (screen_x, screen_y))

    def draw_ships(self, ships, camera_x, camera_y):
        for ship in ships:
            screen_x = ship.rect.center[0] - camera_x
            screen_y = ship.rect.center[1] - camera_y

            if ship.player:
                if ship.thrusting:
                    rotated_sprite = pygame.transform.rotate(self.player_ship_moving_sprite, ship.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)
                else:
                    rotated_sprite = pygame.transform.rotate(self.player_ship_sprite, ship.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)
            else:
                rotated_sprite = pygame.transform.rotate(self.enemy_ship_sprite, ship.heading)
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)

    def draw_pirates(self, pirates, camera_x, camera_y):
        for cell in pirates.values():
            for pirate in cell:
                screen_x = pirate.rect.center[0] - camera_x
                screen_y = pirate.rect.center[1] - camera_y

                if pirate.ambushing:
                    rotated_sprite = pygame.transform.rotate(self.pirate_ship_ambushing, pirate.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)
                else:
                    rotated_sprite = pygame.transform.rotate(self.pirate_ship_sprite, pirate.heading)
                    rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                    self.screen.blit(rotated_sprite, rotated_rect)

    def draw_bullets(self, bullets, camera_x, camera_y):
        for bullet in bullets:
            screen_x = bullet.pos_x - camera_x
            screen_y = bullet.pos_y - camera_y
            pygame.draw.circle(self.screen, bullet.color, (screen_x, screen_y), 2)

    def draw_end_game(self, message="SIGNAL LOST", subtitle="SYNCHRONIZATION LOST. DEBUG:42*1a2"):
        w, h = self.screen.get_width(), self.screen.get_height()
        t = time.time()

        # Base phosphor colors
        PHOSPHOR = (0, 200, 50)
        PHOSPHOR_DIM = (0, 90, 60)
        PHOSPHOR_DARK = (0, 50, 25)

        if not hasattr(self, "_sig_font"):
            self._sig_font = pygame.font.Font(None, 130)
            self._sig_font_sub = pygame.font.Font(None, 40)
            self._diag_font = pygame.font.Font(None, 24)  # New font for diagnostics

        # 1. Dead feed: wash to the UI's own black-green.
        wash = pygame.Surface((w, h), pygame.SRCALPHA)
        wash.fill((2, 8, 2, 235))
        self.screen.blit(wash, (0, 0))

        # 2. Grid & Sonar Sweep (Drone Interface)
        # Faint tactical grid
        grid = pygame.Surface((w, h), pygame.SRCALPHA)
        grid_spacing = 60
        for x in range(0, w, grid_spacing):
            pygame.draw.line(grid, PHOSPHOR_DARK, (x, 0), (x, h), 1)
        for y in range(0, h, grid_spacing):
            pygame.draw.line(grid, PHOSPHOR_DARK, (0, y), (w, y), 1)

        # Center crosshair
        cx, cy = w // 2, h // 2
        pygame.draw.circle(grid, PHOSPHOR_DIM, (cx, cy), 150, 1)
        pygame.draw.line(grid, PHOSPHOR_DIM, (cx - 170, cy), (cx + 170, cy), 1)
        pygame.draw.line(grid, PHOSPHOR_DIM, (cx, cy - 170), (cx, cy + 170), 1)

        # Sweeping radar/sonar line looking for connection
        sweep_angle = t * 3  # Speed of rotation
        sx = cx + math.cos(sweep_angle) * w
        sy = cy + math.sin(sweep_angle) * w
        pygame.draw.line(grid, PHOSPHOR_DIM, (cx, cy), (sx, sy), 2)
        self.screen.blit(grid, (0, 0))

        # 3. Monochrome phosphor snow
        noise = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(160):
            nx = random.randint(0, w)
            ny = random.randint(0, h)
            v = random.randint(20, 70)
            pygame.draw.rect(noise, (0, v + 40, v, v), (nx, ny, 2, 2))
        self.screen.blit(noise, (0, 0))

        # 4. Gentle phosphor flicker
        flicker = 0.82 + 0.18 * math.sin(t * 14)

        # 5. Diagnostic overlay (Top Left)
        # Randomizing the hex code slightly based on time to look like it's churning
        err_code = hex(int(t * 100) % 0xFFFF)[2:].upper()
        diagnostics = [
            "UPLINK_NODE_04 ... FAIL",
            "TELEMETRY      ... NO CARRIER",
            "PNEUMATICS     ... OFFLINE",
            "SONAR_PING     ... TIMEOUT",
            f"SYS_ERR_LOG    ... 0x{err_code}"
        ]

        dy = 20
        for msg in diagnostics:
            diag_surf = self._diag_font.render(msg, True, PHOSPHOR_DIM)
            diag_surf.set_alpha(int(200 * flicker))
            self.screen.blit(diag_surf, (20, dy))
            dy += 22

        # 6. Title with soft monochrome bloom
        core = self._sig_font.render(message, True, PHOSPHOR)
        halo = self._sig_font.render(message, True, PHOSPHOR_DIM)
        core.set_alpha(int(255 * flicker))
        halo.set_alpha(int(150 * flicker))
        tw, th = core.get_width(), core.get_height()
        tx = w // 2 - tw // 2
        ty = h // 2 - th // 2 - 20

        # Draw halo slightly offset
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            self.screen.blit(halo, (tx + ox, ty + oy))
        self.screen.blit(core, (tx, ty))

        # 7. Subtitle with a blinking underscore cursor
        cursor = "_" if int(t * 2) % 2 == 0 else " "
        sub = self._sig_font_sub.render(f"> {subtitle} {cursor}", True, PHOSPHOR)
        sub.set_alpha(int(220 * flicker))
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, ty + th + 16))

        # 8. Reconnection attempt text (Bottom Left)
        attempt_num = int(t * 0.5) % 99
        dots = "." * (int(t * 3) % 4)
        reconnect_txt = f"AUTO-RECONNECT ATTEMPT {attempt_num:02d}/99{dots}"
        reconnect_surf = self._diag_font.render(reconnect_txt, True, PHOSPHOR)
        reconnect_surf.set_alpha(int(255 * flicker))
        self.screen.blit(reconnect_surf, (20, h - 30))

        # 9. One bright monochrome tear line sweeping slowly down the tube
        tear_y = int((t * 90) % h)
        tear = pygame.Surface((w, 3), pygame.SRCALPHA)
        tear.fill((0, 255, 160, 45))
        self.screen.blit(tear, (0, tear_y))

        # 10. Scanlines to seat it in the glass
        scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(scan, (0, 0, 0, 110), (0, y), (w, y), 2)
        self.screen.blit(scan, (0, 0))

    def draw_ftl_jump_tunnel(self, ftl_jumping):
        """Draw a hyperspace warp effect implying FTL speed, with a retro UI."""
        if not ftl_jumping:
            # Clear the particle system when FTL ends
            if hasattr(self, 'ftl_particles'):
                del self.ftl_particles
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        center_x = screen_width // 2
        center_y = screen_height // 2
        max_radius = math.hypot(center_x, center_y)

        # 1. Initialize the particle system (Unchanged)
        if not hasattr(self, 'ftl_particles'):
            self.ftl_particles = []
            for _ in range(150):
                angle = random.uniform(0, 2 * math.pi)
                radius = random.uniform(10, max_radius)
                speed = random.uniform(2, 10)
                color = random.choice([
                    (200, 255, 255),
                    (100, 150, 255),
                    (255, 255, 255)
                ])
                self.ftl_particles.append([angle, radius, speed, color])

        # 2. Update and draw the warp streaks (Unchanged)
        for p in self.ftl_particles:
            angle, radius, speed, color = p

            tail_length = speed * 2.5
            tail_radius = max(1, radius - tail_length)

            x1 = center_x + math.cos(angle) * tail_radius
            y1 = center_y + math.sin(angle) * tail_radius
            x2 = center_x + math.cos(angle) * radius
            y2 = center_y + math.sin(angle) * radius

            thickness = int((radius / max_radius) * 4) + 1
            pygame.draw.line(self.screen, color, (int(x1), int(y1)), (int(x2), int(y2)), thickness)

            p[2] *= 1.08
            p[1] += p[2]

            if p[1] > max_radius * 1.2:
                p[0] = random.uniform(0, 2 * math.pi)
                p[1] = random.uniform(1, 15)
                p[2] = random.uniform(1, 4)

        # 3. Dashboard Text - Low-fidelity terminal styling
        if not hasattr(self, 'font_ftl'):
            # Force a chunky monospace font rather than the smooth default
            self.font_ftl = pygame.font.SysFont('courier', 42, bold=True)

        # Hard on/off blink every 500ms instead of a smooth sine wave
        is_blink_on = (pygame.time.get_ticks() // 500) % 2 == 0

        if is_blink_on:
            ui_color = (50, 255, 50)  # High-contrast terminal green

            # Anti-aliasing set to False (the middle argument) for pixelated edges
            ftl_text = self.font_ftl.render("JUMP SOLUTION: FIXED", False, ui_color)

            text_x = center_x - ftl_text.get_width() // 2
            text_y = screen_height - (screen_height // 4)

            # Calculate bounding box with padding
            pad_x, pad_y = 24, 12
            box_rect = pygame.Rect(
                text_x - pad_x,
                text_y - pad_y,
                ftl_text.get_width() + (pad_x * 2),
                ftl_text.get_height() + (pad_y * 2)
            )

            # Draw solid black background to block out warp streaks, then draw border
            pygame.draw.rect(self.screen, (0, 0, 0), box_rect)
            pygame.draw.rect(self.screen, ui_color, box_rect, width=3)

            # Blit the text on top
            self.screen.blit(ftl_text, (text_x, text_y))

    def draw_ship_arrival(self, ship_position, arrival_timer, camera_x, camera_y, max_duration=1.0):
        """Draw high-energy impact burst with directional spike lines radiating outward."""
        if arrival_timer <= 0.0 or arrival_timer >= max_duration:
            return

        progress = max(0.0, min(1.0, arrival_timer / max_duration))

        # Convert world coordinates to screen coordinates
        sx = int(ship_position[0] - camera_x)
        sy = int(ship_position[1] - camera_y)

        alpha = int(255 * (1.0 - progress))
        if alpha <= 0:
            return

        # Canvas size to contain the exploding lines
        max_reach = 180
        surf_size = max_reach * 2 + 20
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = (surf_size // 2, surf_size // 2)

        # 1. Immediate Impact Core (Hot white/cyan flash at center)
        if progress < 0.25:
            core_p = progress / 0.25
            core_radius = int(25 * math.sin(core_p * math.pi))
            if core_radius > 0:
                pygame.draw.circle(surf, (255, 255, 255, alpha), center, core_radius)
                pygame.draw.circle(surf, (0, 220, 255, int(alpha * 0.6)), center, core_radius + 8, width=2)

        # 2. Exploding Spike Lines
        num_spikes = 16
        for i in range(num_spikes):
            # Seed generator per spike so paths remain consistent frame-to-frame
            rng = random.Random(i * 307)
            angle = rng.uniform(0, math.tau)
            max_length = rng.uniform(80, max_reach)
            speed = rng.uniform(0.85, 1.15)
            color_choice = rng.choice([(255, 255, 255), (0, 220, 255), (100, 180, 255)])

            # Fast outward movement with ease-out deceleration
            eased_p = math.sin((progress * speed) * (math.pi / 2))

            # Line start/end points travel outward together to create flying streaks
            dist_head = eased_p * max_length
            dist_tail = max(0.0, dist_head - (35 * (1.0 - progress)))

            x1 = center[0] + int(math.cos(angle) * dist_tail)
            y1 = center[1] + int(math.sin(angle) * dist_tail)
            x2 = center[0] + int(math.cos(angle) * dist_head)
            y2 = center[1] + int(math.sin(angle) * dist_head)

            line_alpha = int(alpha * rng.uniform(0.7, 1.0))
            if line_alpha > 0 and dist_head > dist_tail:
                pygame.draw.line(surf, (*color_choice, line_alpha), (x1, y1), (x2, y2), width=2)

        # 3. Outer Shockwave Edge (Thin, fast high-contrast shock ring)
        shock_r = int(progress * (max_reach * 0.8))
        if shock_r > 0:
            pygame.draw.circle(surf, (180, 240, 255, int(alpha * 0.4)), center, shock_r, width=1)

        # Blit centered on screen coordinates
        self.screen.blit(surf, (sx - center[0], sy - center[1]))

    def draw_ship_analysis(self, ship_position, arrival_timer, camera_x, camera_y, max_duration=1.0):
        """Draw a diagnostic targeting sequence with a callout debug terminal."""
        if arrival_timer <= 0.0 or arrival_timer >= max_duration:
            return

        progress = max(0.0, min(1.0, arrival_timer / max_duration))

        sx = int(ship_position[0] - camera_x)
        sy = int(ship_position[1] - camera_y)

        alpha = 255 if progress < 0.85 else int(255 * (1.0 - (progress - 0.85) / 0.15))
        if alpha <= 0:
            return

        # Canvas setup - Expanded to 400x400 to fit the external callout UI
        box_size = 70
        surf_size = 400
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = (surf_size // 2, surf_size // 2)

        ui_green = (50, 255, 50)
        ui_bright = (180, 255, 180)
        ui_faint = (20, 100, 20)

        # 1. Target Acquisition Box
        box_p = min(1.0, progress * 5.0)
        current_radius = int((box_size // 2) + 20 * (1.0 - math.sin(box_p * math.pi / 2)))

        # 2. Diagnostic Grid Overlay
        if progress > 0.1:
            grid_step = 10
            for i in range(-current_radius, current_radius + 1, grid_step):
                pygame.draw.line(surf, (*ui_faint, alpha),
                                 (center[0] + i, center[1] - current_radius),
                                 (center[0] + i, center[1] + current_radius), 1)
                pygame.draw.line(surf, (*ui_faint, alpha),
                                 (center[0] - current_radius, center[1] + i),
                                 (center[0] + current_radius, center[1] + i), 1)

        # 3. Target Brackets
        b_len = 12
        for bx, by in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            cx = center[0] + (current_radius * bx)
            cy = center[1] + (current_radius * by)
            pygame.draw.line(surf, (*ui_bright, alpha), (cx, cy), (cx - (b_len * bx), cy), 2)
            pygame.draw.line(surf, (*ui_bright, alpha), (cx, cy), (cx, cy - (b_len * by)), 2)

        # 4. Scanning Sweep
        if 0.2 < progress < 0.9:
            scan_p = (progress - 0.2) / 0.7
            scan_y = center[1] - current_radius + int((current_radius * 2) * scan_p)

            pygame.draw.line(surf, (*ui_bright, alpha),
                             (center[0] - current_radius, scan_y),
                             (center[0] + current_radius, scan_y), 2)
            pygame.draw.rect(surf, (*ui_green, int(alpha * 0.25)),
                             (center[0] - current_radius, scan_y - 12, current_radius * 2, 12))

        # 5. Data Readout Waterfall & Progress Bar
        if progress > 0.3:
            scroll_offset = int(arrival_timer * 60) % 8
            block_x = center[0] + current_radius + 8
            start_y = center[1] - current_radius + scroll_offset

            for y in range(start_y, center[1] + current_radius, 8):
                data_w = 6 + ((y * 7) % 24)
                if y + 4 <= center[1] + current_radius:
                    pygame.draw.rect(surf, (*ui_green, alpha), (block_x, y, data_w, 4))

            bar_w = int((current_radius * 2) * progress)
            bar_y = center[1] + current_radius + 8
            pygame.draw.rect(surf, (*ui_faint, alpha), (center[0] - current_radius, bar_y, current_radius * 2, 4))
            pygame.draw.rect(surf, (*ui_bright, alpha), (center[0] - current_radius, bar_y, bar_w, 4))

        # 6. Diagonal Callout Line & Debug Console
        if progress > 0.4:
            # Define the path for the line: Start -> Diagonal elbow -> Horizontal end
            call_start = (center[0] + current_radius, center[1] - current_radius + 10)
            call_elbow = (call_start[0] + 35, call_start[1] - 35)
            call_end = (call_elbow[0] + 20, call_elbow[1])

            pygame.draw.line(surf, (*ui_bright, alpha), call_start, call_elbow, 1)
            pygame.draw.line(surf, (*ui_bright, alpha), call_elbow, call_end, 1)

            # Draw the rigid terminal box at the end of the line
            box_width, box_height = 110, 64
            box_rect = pygame.Rect(call_end[0], call_end[1] - 10, box_width, box_height)

            # Black fill prevents background stars/grid from muddying the text
            pygame.draw.rect(surf, (0, 0, 0, alpha), box_rect)
            pygame.draw.rect(surf, (*ui_green, alpha), box_rect, 1)

            # Load monospace font once
            if not hasattr(self, '_diag_font'):
                self._diag_font = pygame.font.SysFont('courier', 12)

            # Generate rapidly scrambling hex values tied to the timer
            # Updating the seed every ~0.08 seconds creates a harsh terminal flicker
            rng = random.Random(int(arrival_timer * 12))
            hex_chars = "0123456789ABCDEF"

            # Draw header
            header = self._diag_font.render("SIG_ANOMALY", False, ui_green)
            header.set_alpha(alpha)
            surf.blit(header, (box_rect.x + 4, box_rect.y + 4))

            # Draw 3 rows of junk hex data
            for row in range(3):
                hex_str = "0x" + "".join(rng.choice(hex_chars) for _ in range(8))
                text_surf = self._diag_font.render(hex_str, False, ui_bright)
                text_surf.set_alpha(alpha)
                surf.blit(text_surf, (box_rect.x + 4, box_rect.y + 20 + (row * 14)))

        # Blit to screen
        self.screen.blit(surf, (sx - center[0], sy - center[1]))

    import pygame
    import random
    import math

    def draw_blink_tunnel(self, ship_position, blink_timer, camera_x, camera_y, max_duration=120):
        """Draw low-tech 1980s CRT blink-space transit effect (2-second duration)."""
        if blink_timer <= 0:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        # Phosphor palette (Classic terminal green & dim retention artifacts)
        PHOSPHOR_GREEN = (0, 255, 70)
        PHOSPHOR_DIM = (0, 90, 25)
        BLACK = (0, 0, 0)

        # Severe 80s CRT hardware jitter / tracking error during deep transit
        jitter_x = random.randint(-2, 2)
        jitter_y = random.randint(-2, 2)

        ship_screen_x = ship_position[0] - camera_x + jitter_x
        ship_screen_y = ship_position[1] - camera_y + jitter_y

        # Progress counts down from 1.0 to 0.0 over the max_duration
        progress = blink_timer / max_duration

        # --- ANIMATION PHASES ---
        # Calculate a scale factor (0.0 to 1.0) to animate the arrival and departure
        if progress > 0.8:
            # First 20% of duration (Departure): expand out from 0.0 to 1.0
            scale = (1.0 - progress) / 0.2
        elif progress < 0.2:
            # Last 20% of duration (Arrival): shrink from 1.0 down to 0.0
            scale = progress / 0.2
        else:
            # Middle 60% of duration (Transit): hold at full size
            scale = 1.0

        max_radius = math.hypot(screen_width // 2, screen_height // 2)

        # 1. High-frequency random digital static / snow
        # Now multiplied by `scale` so the static stays confined to the diamond's current size
        static_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        for _ in range(40):
            sx = ship_screen_x + random.uniform(-max_radius * scale, max_radius * scale)
            sy = ship_screen_y + random.uniform(-max_radius * scale, max_radius * scale)
            pygame.draw.circle(static_surface, (*PHOSPHOR_DIM, random.randint(100, 200)), (int(sx), int(sy)), 1)
        self.screen.blit(static_surface, (0, 0))

        # 2. Opaque Diamond / Radar Sweep
        grid_size = int(max_radius * scale)
        if grid_size > 5:
            # Define the 4 points of the diamond relative to the ship's center
            diamond_points = [
                (ship_screen_x, ship_screen_y - grid_size),  # Top
                (ship_screen_x + grid_size, ship_screen_y),  # Right
                (ship_screen_x, ship_screen_y + grid_size),  # Bottom
                (ship_screen_x - grid_size, ship_screen_y)  # Left
            ]

            # Draw a solid black polygon first to block out the background stars
            pygame.draw.polygon(self.screen, BLACK, diamond_points)

            # Draw the phosphor green outline of the diamond
            pygame.draw.polygon(self.screen, PHOSPHOR_DIM, diamond_points, 1)

            # Vector intersection lines (crosshairs inside the diamond)
            pygame.draw.line(self.screen, PHOSPHOR_DIM,
                             (ship_screen_x, ship_screen_y - grid_size),
                             (ship_screen_x, ship_screen_y + grid_size), 1)
            pygame.draw.line(self.screen, PHOSPHOR_DIM,
                             (ship_screen_x - grid_size, ship_screen_y),
                             (ship_screen_x + grid_size, ship_screen_y), 1)

        # 3. Retro Terminal Text & Telemetry UI
        if not hasattr(self, 'font_blink'):
            self.font_blink = pygame.font.SysFont("Courier", 18, bold=True)

        # Display countdown frames and status
        time_left_sec = max(0.0, blink_timer / 60.0)
        status_str = f"BLINK_SPACE // T-{time_left_sec:.1f}s"

        text_surf = self.font_blink.render(status_str, True, PHOSPHOR_GREEN)
        text_x = int(ship_screen_x) - text_surf.get_width() // 2
        text_y = int(ship_screen_y) - 45

        box_rect = pygame.Rect(
            text_x - 8,
            text_y - 4,
            text_surf.get_width() + 16,
            text_surf.get_height() + 8
        )

        # Solid black cutout box for sharp vector UI isolation
        pygame.draw.rect(self.screen, BLACK, box_rect)
        pygame.draw.rect(self.screen, PHOSPHOR_GREEN, box_rect, 1)

        self.screen.blit(text_surf, (text_x, text_y))

        # 4. CRT Horizontal Scanlines Overlay (Full screen pass)
        scanline_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        for y in range(0, screen_height, 3):
            pygame.draw.line(scanline_surface, (0, 0, 0, 120), (0, y), (screen_width, y), 1)

        self.screen.blit(scanline_surface, (0, 0))
