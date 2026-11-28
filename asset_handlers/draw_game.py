import math
import random
import pygame
import sys
import os

from config import theme
from config.constants import SELF_MIN_ALPHA
from asset_handlers import fonts
from objects.explosion import FLASH_COLOR, phosphor_color
from pathlib import Path

# Below this speed a turning ship uses the rotate-in-place sprites
ROTATE_SPRITE_MAX_SPEED = 10

# Asteroid (outline, body) colours by material; rocky is the default in theme
ASTEROID_COLORS = {
    'metallic': theme.ASTEROID_METALLIC,
    'semi-metallic': theme.ASTEROID_SEMI_METALLIC,
    'icy': theme.ASTEROID_ICY,
}


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

    # Check if within the viewport
    return (world_left < screen_x < world_right and
            world_top < screen_y < world_bottom)


class DrawGame:
    def __init__(self, screen, world_width, world_height):
        self.font_ftl = None
        self.ftl_particles = None

        self.screen = screen
        if getattr(sys, "frozen", False):
            base_path = Path(sys._MEIPASS)  # noqa
        else:
            base_path = Path(__file__).resolve().parent.parent

        asset_path = base_path / "assets"
        self.ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship.png"))
        self.ship_forward_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_forward.png"))
        self.ship_backward_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_backward.png"))
        self.ship_forward_left_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_forward_left.png"))
        self.ship_forward_right_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_forward_right.png"))
        self.ship_backward_left_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_backward_left.png"))
        self.ship_backward_right_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_backward_right.png"))
        self.ship_rotate_right_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_rotate_right.png"))
        self.ship_rotate_left_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_rotate_left.png"))
        self.ship_translate_left = pygame.image.load(os.path.join(asset_path, "pngs/ship_translate_left.png"))
        self.ship_translate_right = pygame.image.load(os.path.join(asset_path, "pngs/ship_translate_right.png"))
        self.ship_invisible_sprite = pygame.image.load(os.path.join(asset_path, "pngs/ship_invisible.png"))

        self.ship_debris = pygame.image.load(os.path.join(asset_path, "pngs/ship_debris.png"))

        self.enemy_ship_sprite = pygame.image.load(os.path.join(asset_path, "pngs/enemy_ship.png"))
        self.missile_sprite = pygame.image.load(os.path.join(asset_path, "pngs/missile.png"))
        self.drone_sprite = pygame.image.load(os.path.join(asset_path, "pngs/drone.png"))
        self.drone_mining_sprite = pygame.image.load(os.path.join(asset_path, "pngs/drone_mining.png"))
        self.decoy_sprite = pygame.image.load(os.path.join(asset_path, "pngs/decoy.png"))
        self.pirate_sprite = pygame.image.load(os.path.join(asset_path, "pngs/pirate.png"))
        self.pirate_ambushing_sprite = pygame.image.load(os.path.join(asset_path, "pngs/pirate_ambushing.png"))

        self.derelict_ship = pygame.image.load(os.path.join(asset_path, "pngs/derelict.png"))
        self.font_asteroid_name = fonts.font(14)

        # Generate starfield
        self.stars = generate_stars(10000, world_width, world_height)

    def draw_stars(self, camera_x, camera_y, show=True):
        """Draw starfield with camera offset"""
        if not show:
            return
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()

        for star_x, star_y, brightness, size in self.stars:
            screen_x = star_x - camera_x
            screen_y = star_y - camera_y

            # Only draw if on screen
            if -10 < screen_x < screen_width + 10 and -10 < screen_y < screen_height + 10:
                tint = theme.STAR_TINT
                color = (brightness * tint[0] // 255, brightness * tint[1] // 255, brightness * tint[2] // 255)
                pygame.draw.circle(self.screen, color, (screen_x, screen_y), size)

    def draw_asteroids(self, asteroids, camera_x, camera_y, show=True):
        if not show:
            return
        for asteroid in asteroids:
            if not is_visible_to_camera(asteroid, camera_x, camera_y, self.screen.get_width(), self.screen.get_height()):
                continue

            screen_x = asteroid.pos_x - camera_x
            screen_y = asteroid.pos_y - camera_y
            outline_color, fill_color = ASTEROID_COLORS.get(
                asteroid.material, (theme.ASTEROID, theme.ASTEROID_FILL))
            points = [(screen_x + ox, screen_y + oy) for ox, oy in asteroid.outline]
            pygame.draw.polygon(self.screen, fill_color, points)
            pygame.draw.polygon(self.screen, outline_color, points, 2)

            if asteroid.id_for_ui is not None:
                name_surf = self.font_asteroid_name.render(str(asteroid.id_for_ui), True, outline_color)
                self.screen.blit(name_surf, name_surf.get_rect(center=(screen_x, screen_y)))

    def draw_explosions(self, explosions, camera_x, camera_y, show=True):
        """Vector-style explosions: a flash, expanding rings and debris lines, in one phosphor colour."""
        if not show:
            return
        for explosion in explosions:
            centre = (explosion.x - camera_x, explosion.y - camera_y)
            flash_radius = explosion.flash_radius()
            if flash_radius >= 1:
                pygame.draw.circle(self.screen, FLASH_COLOR, centre, int(flash_radius))
            ring_color = phosphor_color(explosion.colour, explosion.fade)
            for radius in explosion.ring_radii():
                if radius >= 1:
                    pygame.draw.circle(self.screen, ring_color, centre, int(radius), 1)
            for x, y, tail_x, tail_y, piece_fade in explosion.debris_points():
                color = phosphor_color(explosion.colour, piece_fade)
                pygame.draw.line(self.screen, color,
                                 (tail_x - camera_x, tail_y - camera_y),
                                 (x - camera_x, y - camera_y))

    def draw_missiles(self, missiles, camera_x, camera_y, show=True):
        if not show:
            return
        for missile in missiles:
            screen_x = missile.pos_x - camera_x
            screen_y = missile.pos_y - camera_y
            rotated_sprite = pygame.transform.rotate(self.missile_sprite, missile.heading)
            rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
            self.screen.blit(rotated_sprite, rotated_rect)

    def draw_drones(self, drones, camera_x, camera_y, show=True):
        if not show:
            return
        for drone in drones:
            if is_visible_to_camera(drone, camera_x, camera_y, self.screen.get_width(), self.screen.get_height()):
                screen_x = drone.pos_x - camera_x
                screen_y = drone.pos_y - camera_y

                if drone.am_mining:
                    self.screen.blit(self.drone_mining_sprite, (screen_x, screen_y))
                else:
                    self.screen.blit(self.drone_sprite, (screen_x, screen_y))

    def draw_decoys(self, decoys, camera_x, camera_y, show=True):
        if not show:
            return
        for decoy in decoys:
            screen_x = decoy.pos_x - camera_x
            screen_y = decoy.pos_y - camera_y
            self.screen.blit(self.decoy_sprite, (screen_x, screen_y))

    def draw_derelicts(self, derelicts, camera_x, camera_y, show=True):
        if not show:
            return
        for derelict in derelicts:
            if is_visible_to_camera(derelict, camera_x, camera_y, self.screen.get_width(), self.screen.get_height()):
                screen_x = derelict.pos_x - camera_x
                screen_y = derelict.pos_y - camera_y
                rect = self.derelict_ship.get_rect(center=(screen_x, screen_y))
                self.screen.blit(self.derelict_ship, rect)

    def pick_player_sprite(self, ship):
        """Choose the player's sprite from a thrust direction, turn input and speed."""
        # Retro is checked first: ship.thrusting is also True during a reverse burn

        if ship.cloaking_value >= 5:
            return self.ship_invisible_sprite

        if ship.translate_left:
            return self.ship_translate_left
        elif ship.translate_right:
            return self.ship_translate_right

        if ship.retro_thrust:
            if ship.rotate_left:
                return self.ship_backward_left_sprite
            if ship.rotate_right:
                return self.ship_backward_right_sprite
            return self.ship_backward_sprite

        if ship.thrusting:
            if ship.rotate_left:
                return self.ship_forward_left_sprite
            if ship.rotate_right:
                return self.ship_forward_right_sprite
            return self.ship_forward_sprite

        # Turning on the spot: no thrust and nearly stopped
        if not ship.thrusting and not ship.retro_thrust:
            if ship.rotate_left:
                return self.ship_rotate_left_sprite
            if ship.rotate_right:
                return self.ship_rotate_right_sprite

        return self.ship_sprite

    def draw_ships(self, ships, camera_x, camera_y, my_id, prox_scan, show=True):
        if not show:
            return
        for ship in ships:
            screen_x = ship.rect.center[0] - camera_x
            screen_y = ship.rect.center[1] - camera_y
            if not ship.alive:
                sprite = pygame.transform.rotate(self.ship_debris, ship.heading)
                rotated_rect = sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(sprite, rotated_rect)
                continue

            if ship.player_id == my_id:
                # Never fainter than SELF_MIN_ALPHA, so you can always find your own ship
                sprite = self.pick_player_sprite(ship)
                rotated_sprite = pygame.transform.rotate(sprite, ship.heading)
                rotated_sprite.set_alpha(max(ship.visibility, SELF_MIN_ALPHA))
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)

            elif prox_scan:
                rotated_sprite = pygame.transform.rotate(self.enemy_ship_sprite, ship.heading)
                if ship.cloaking_value == 5:
                    continue
                rotated_sprite.set_alpha(ship.visibility)
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)

    def draw_pirates(self, pirates, camera_x, camera_y, show=True):
        if not show:
            return
        for pirate in pirates:
            screen_x = pirate.rect.center[0] - camera_x
            screen_y = pirate.rect.center[1] - camera_y

            if pirate.resting:
                rotated_sprite = pygame.transform.rotate(self.pirate_ambushing_sprite, pirate.heading)
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)
            else:
                rotated_sprite = pygame.transform.rotate(self.pirate_sprite, pirate.heading)
                rotated_rect = rotated_sprite.get_rect(center=(screen_x, screen_y))
                self.screen.blit(rotated_sprite, rotated_rect)

    def draw_bullets(self, bullets, camera_x, camera_y, show=True):
        if not show:
            return
        for bullet in bullets:
            screen_x = bullet.pos_x - camera_x
            screen_y = bullet.pos_y - camera_y
            # Phosphor persistence: a short tracer trail that dims toward black behind the round
            speed = math.hypot(bullet.vel_x, bullet.vel_y)
            if speed > 0:
                ux, uy = -bullet.vel_x / speed, -bullet.vel_y / speed
                length = theme.BULLET_TRAIL_LENGTH
                steps = 3
                for k in range(steps):
                    near = length * k / steps
                    far = length * (k + 1) / steps
                    fade = 1 - (k + 0.5) / steps
                    trail = tuple(int(c * fade) for c in bullet.color)
                    pygame.draw.line(self.screen, trail,
                                     (screen_x + ux * near, screen_y + uy * near),
                                     (screen_x + ux * far, screen_y + uy * far), 2)
            pygame.draw.circle(self.screen, bullet.color, (screen_x, screen_y), 2)

    def draw_ftl_jump_tunnel(self, ftl_jumping, show=True):
        """Draw a hyperspace warp effect implying FTL speed, with a retro UI."""
        if not show:
            return
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
                    theme.WHITE,
                    theme.GREEN_BRIGHT,
                    theme.GREEN_DIM,
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
        self.font_ftl = fonts.font(44)

        # Hard on/off blink every 500ms instead of a smooth sine wave
        is_blink_on = (pygame.time.get_ticks() // 500) % 2 == 0

        if is_blink_on:
            ui_color = theme.GREEN

            # Antialiasing set to False (the middle argument) for pixelated edges
            ftl_text = self.font_ftl.render("JUMP SOLUTION: FIXED", True, ui_color)

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
            pygame.draw.rect(self.screen, theme.BLACK, box_rect)
            pygame.draw.rect(self.screen, ui_color, box_rect, width=3)

            # Blit the text on top
            self.screen.blit(ftl_text, (text_x, text_y))

    def draw_ftl_arrival(self, ship_position, arrival_timer, camera_x, camera_y, max_duration=1.0, show=True):
        """Draw a high-impact FTL arrival: rupture flash, spike burst, and stacked shock waves."""
        if not show:
            return
        if arrival_timer <= 0.0 or arrival_timer >= max_duration:
            return

        progress = max(0.0, min(1.0, arrival_timer / max_duration))

        sx = int(ship_position[0] - camera_x)
        sy = int(ship_position[1] - camera_y)

        alpha = int(255 * (1.0 - progress))
        if alpha <= 0:
            return

        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        # --- 0. Rupture flash: brief full-frame wash as the ship tears in ---
        # Only in the first ~15% so it reads as the moment of arrival, not a fade.
        if progress < 0.15:
            flash_p = 1.0 - (progress / 0.15)
            flash_alpha = int(220 * flash_p)
            flash = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            flash.fill((*theme.WHITE, flash_alpha))
            self.screen.blit(flash, (0, 0))

        # Canvas for the radial elements
        max_reach = 260
        surf_size = max_reach * 2 + 20
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = (surf_size // 2, surf_size // 2)

        # --- 1. Impact core: hot flash that lingers longer than before ---
        if progress < 0.4:
            core_p = progress / 0.4
            core_radius = int(40 * math.sin(core_p * math.pi))
            if core_radius > 0:
                pygame.draw.circle(surf, (*theme.WHITE, alpha), center, core_radius)
                pygame.draw.circle(surf, (*theme.GREEN, int(alpha * 0.7)), center, core_radius + 12, width=3)
                pygame.draw.circle(surf, (*theme.GREEN_DIM, int(alpha * 0.35)), center, core_radius + 24, width=2)

        # --- 2. Exploding spike lines with bright leading heads ---
        num_spikes = 26
        for i in range(num_spikes):
            rng = random.Random(i * 307)
            angle = rng.uniform(0, math.tau)
            max_length = rng.uniform(120, max_reach)
            speed = rng.uniform(0.85, 1.15)
            color_choice = rng.choice([theme.WHITE, theme.GREEN, theme.GREEN_BRIGHT, theme.WHITE])

            eased_p = math.sin((progress * speed) * (math.pi / 2))
            dist_head = eased_p * max_length
            # Longer tails for a stronger sense of speed
            dist_tail = max(0.0, dist_head - (55 * (1.0 - progress)))

            x1 = center[0] + int(math.cos(angle) * dist_tail)
            y1 = center[1] + int(math.sin(angle) * dist_tail)
            x2 = center[0] + int(math.cos(angle) * dist_head)
            y2 = center[1] + int(math.sin(angle) * dist_head)

            line_alpha = int(alpha * rng.uniform(0.7, 1.0))
            if line_alpha > 0 and dist_head > dist_tail:
                pygame.draw.line(surf, (*color_choice, line_alpha), (x1, y1), (x2, y2), width=2)
                # Bright head dot at the leading tip
                pygame.draw.circle(surf, (*theme.WHITE, line_alpha), (x2, y2), 2)

        # --- 3. Stacked shock waves: three rings released in sequence ---
        for wave in range(3):
            wave_delay = wave * 0.12
            wave_p = (progress - wave_delay) / (1.0 - wave_delay) if progress > wave_delay else -1.0
            if 0.0 < wave_p < 1.0:
                shock_r = int(wave_p * max_reach)
                shock_alpha = int(alpha * (1.0 - wave_p) * 0.6)
                if shock_r > 0 and shock_alpha > 0:
                    pygame.draw.circle(surf, (*theme.GREEN_BRIGHT, shock_alpha), center, shock_r, width=2)

        self.screen.blit(surf, (sx - center[0], sy - center[1]))

    def draw_blink_arrival(self, ship_position, arrival_timer, camera_x, camera_y, max_duration=1.0, show=True):
        """Blink exit: a reticle closes on the ship, one ring pings out, and a readout confirms the lock."""
        if not show:
            return
        if arrival_timer <= 0.0 or arrival_timer >= max_duration:
            return

        progress = max(0.0, min(1.0, arrival_timer / max_duration))

        sx = int(ship_position[0] - camera_x)
        sy = int(ship_position[1] - camera_y)

        alpha = int(255 * (1.0 - progress))
        if alpha <= 0:
            return

        surf_size = 400
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = (surf_size // 2, surf_size // 2)

        # 1. Reticle: four corner brackets close from wide to tight on the ship over the first 40%
        close_p = min(1.0, progress / 0.4)
        ease = 1.0 - (1.0 - close_p) ** 3
        half = int(90 - 50 * ease)
        arm = 12
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            cx = center[0] + dx * half
            cy = center[1] + dy * half
            pygame.draw.line(surf, (*theme.WHITE, alpha), (cx, cy), (cx + arm * -dx, cy), 2)
            pygame.draw.line(surf, (*theme.WHITE, alpha), (cx, cy), (cx, cy + arm * -dy), 2)

        # 2. One thin ping ring expanding outwardly and fading
        ring_r = int(40 + progress * 150)
        pygame.draw.circle(surf, (*theme.GREEN, int(alpha * 0.6)), center, ring_r, width=1)

        self.screen.blit(surf, (sx - center[0], sy - center[1]))

        # 3. Readout below the reticle: plain text like the charge meter, holds then fades out
        text_alpha = 255 if progress < 0.6 else int(255 * (1.0 - (progress - 0.6) / 0.4))
        if text_alpha > 0:
            text_surf = fonts.font(16).render("BLINK COMPLETE // POS LOCKED", True, theme.GREEN)
            text_surf.set_alpha(text_alpha)
            self.screen.blit(text_surf, text_surf.get_rect(midtop=(sx, sy + 100)))

    def draw_charge_animation(self, is_charging, charge_timer, max_charge_time=2.0, show=True):
        if not show:
            return
        if not is_charging or charge_timer <= 0:
            return

        screen_x = self.screen.get_width() // 2
        screen_y = self.screen.get_height() // 2
        progress = min(1.0, charge_timer / max_charge_time)

        ready = progress >= 1.0
        accent = theme.AMBER_BRIGHT if ready else theme.GREEN

        # |####----------------| : filled cells, then empty ones
        cells = 20
        filled = int(cells * progress)
        bar = "|" + "#" * filled + "-" * (cells - filled) + "|"
        text = f"BLINK READY {bar}" if ready else f"CHARGING {bar} {int(progress * 100):3d}%"

        surf = fonts.font(16).render(text, True, accent)
        # Well below the ship (which sits at a screen centre), so nothing is drawn over it
        rect = surf.get_rect(midtop=(screen_x, screen_y + 90))
        self.screen.blit(surf, rect)

    def draw_laser(self, lasers, camera, show=True):

        if not show:
            return
        camera_x, camera_y = camera

        # Hotter color profile: white core, vibrant inner red, deep outer red glow
        LASER_CORE = theme.WHITE
        LASER_GLOW_INNER = theme.RED_BRIGHT
        LASER_GLOW_OUTER = theme.RED_DIM

        for laser in lasers:
            ship, end, t = laser.vessel, laser.end, laser.time_left

            sx = int(ship.rect.center[0] - camera_x)
            sy = int(ship.rect.center[1] - camera_y)
            ex = int(end[0] - camera_x)
            ey = int(end[1] - camera_y)

            # Beam: 3 layers for a richer, more intense gradient
            pygame.draw.line(self.screen, LASER_GLOW_OUTER, (sx, sy), (ex, ey), 8)
            pygame.draw.line(self.screen, LASER_GLOW_INNER, (sx, sy), (ex, ey), 4)
            pygame.draw.line(self.screen, LASER_CORE, (sx, sy), (ex, ey), 2)

            # Impact animation
            pulse = (t * 3) % 1.0  # 0 -> 1, repeating
            radius = int(4 + pulse * 12)  # grows slightly larger now (4 -> 16 px)
            alpha = int(255 * (1.0 - pulse))  # fades as it grows

            # Surface expanded slightly to accommodate the larger radius
            ring = pygame.Surface((40, 40), pygame.SRCALPHA)

            # Impact ring
            pygame.draw.circle(ring, (*LASER_GLOW_INNER, alpha), (20, 20), radius, 2)

            # Impact flare: a crosshair that shrinks/flickers as the ring expands
            flare_size = 6 - int(pulse * 4)
            if flare_size > 0:
                pygame.draw.line(ring, (*LASER_CORE, alpha), (20 - flare_size, 20), (20 + flare_size, 20), 1)
                pygame.draw.line(ring, (*LASER_CORE, alpha), (20, 20 - flare_size), (20, 20 + flare_size), 1)

            self.screen.blit(ring, (ex - 20, ey - 20))

            # Two-tone hot spot at the exact contact point
            pygame.draw.circle(self.screen, LASER_GLOW_INNER, (ex, ey), 4)
            pygame.draw.circle(self.screen, LASER_CORE, (ex, ey), 2)
