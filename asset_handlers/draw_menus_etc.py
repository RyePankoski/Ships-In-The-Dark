import pygame
import random

class DrawMenusEtc:
    def __init__(self, screen):
        self.screen = screen

    def draw_splash_screen(self, enabled: bool, timer: float):
        if not enabled:
            return

        import math
        import pygame

        w, h = self.screen.get_size()

        # ------------------------------------------------------------------
        # Colors
        # ------------------------------------------------------------------
        BRIGHT = (90, 255, 120)
        GREEN = (55, 200, 90)
        DIM = (25, 90, 35)

        # ------------------------------------------------------------------
        # Fonts
        # ------------------------------------------------------------------
        title_font = pygame.font.SysFont("couriernew", 96, bold=True)
        sub_font = pygame.font.SysFont("couriernew", 24)
        boot_font = pygame.font.SysFont("couriernew", 22)

        # ------------------------------------------------------------------
        # Background
        # ------------------------------------------------------------------
        self.screen.fill((0, 0, 0))

        # Subtle CRT brightness flicker
        flicker = 0.96 + math.sin(timer * 35.0) * 0.02

        # ------------------------------------------------------------------
        # Wireframe Eye Logo
        # ------------------------------------------------------------------
        logo_alpha = min(timer / 0.8, 1.0)

        logo = pygame.Surface((900, 260), pygame.SRCALPHA)

        c = (
            int(BRIGHT[0] * flicker),
            int(BRIGHT[1] * flicker),
            int(BRIGHT[2] * flicker),
            int(255 * logo_alpha),
        )

        cx = 450
        cy = 120

        # Outer eye
        pygame.draw.arc(
            logo,
            c,
            (120, 40, 660, 160),
            math.pi,
            math.tau,
            3,
        )

        pygame.draw.arc(
            logo,
            c,
            (120, 40, 660, 160),
            0,
            math.pi,
            3,
        )

        # Iris
        pygame.draw.circle(
            logo,
            c,
            (cx, cy),
            42,
            3,
        )

        # Pupil
        pygame.draw.circle(
            logo,
            c,
            (cx, cy),
            12,
        )

        # Crosshair
        pygame.draw.line(
            logo,
            c,
            (cx - 24, cy),
            (cx + 24, cy),
            2,
        )

        pygame.draw.line(
            logo,
            c,
            (cx, cy - 24),
            (cx, cy + 24),
            2,
        )

        logo_rect = logo.get_rect(center=(w // 2, 170))
        self.screen.blit(logo, logo_rect)

        # ------------------------------------------------------------------
        # Company Name
        # ------------------------------------------------------------------
        title = title_font.render(
            "ERGOT SYSTEMS",
            True,
            (
                int(BRIGHT[0] * flicker),
                int(BRIGHT[1] * flicker),
                int(BRIGHT[2] * flicker),
            ),
        )

        self.screen.blit(
            title,
            title.get_rect(center=(w // 2, 330)),
        )

        subtitle = sub_font.render(
            "INTERSTELLAR COMPUTING DIVISION",
            True,
            DIM,
        )

        self.screen.blit(
            subtitle,
            subtitle.get_rect(center=(w // 2, 375)),
        )

        # ------------------------------------------------------------------
        # Boot Messages
        # ------------------------------------------------------------------
        lines = [
            "INITIALIZING MEMORY.....................OK",
            "CALIBRATING SENSOR ARRAY................OK",
            "LINKING DEEP SPACE TELEMETRY............OK",
            "VERIFYING NAVIGATION DATABASE...........OK",
            "BOOTING FLIGHT COMPUTER.................OK",
            "SYSTEM READY.",
        ]

        boot_start = 1.1
        line_delay = 0.48

        x = w // 2 - 310
        y = 460

        for i, line in enumerate(lines):

            reveal = timer - (boot_start + i * line_delay)

            if reveal <= 0:
                continue

            chars = min(len(line), int(reveal * 42))

            surf = boot_font.render(
                "> " + line[:chars],
                True,
                GREEN,
            )

            self.screen.blit(
                surf,
                (x, y + i * 30),
            )

        # ------------------------------------------------------------------
        # Press Any Key
        # ------------------------------------------------------------------
        if timer > 4.2:

            if int(timer * 2.5) % 2 == 0:
                msg = boot_font.render(
                    "PRESS ANY KEY _",
                    True,
                    BRIGHT,
                )

                self.screen.blit(
                    msg,
                    msg.get_rect(center=(w // 2, h - 90)),
                )

        # ------------------------------------------------------------------
        # Scanlines
        # ------------------------------------------------------------------
        scan = pygame.Surface((w, h), pygame.SRCALPHA)

        for yy in range(0, h, 3):
            pygame.draw.line(
                scan,
                (0, 0, 0, 40),
                (0, yy),
                (w, yy),
            )

        self.screen.blit(scan, (0, 0))

        # ------------------------------------------------------------------
        # CRT Vignette
        # ------------------------------------------------------------------
        vignette = pygame.Surface((w, h), pygame.SRCALPHA)

        pygame.draw.rect(
            vignette,
            (0, 0, 0, 80),
            vignette.get_rect(),
            width=28,
            border_radius=16,
        )

        self.screen.blit(vignette, (0, 0))