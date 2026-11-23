import pygame
import os

from utility.paths import asset_dir


class AudioManager:
    # Channel 0 is reserved for looping ambience. Each SFX gets its own
    # dedicated channel starting from FIRST_SFX_CHANNEL, so distinct sounds
    # never share a channel (they can all play at once) and "is this sound
    # already playing?" is just that channel's busy state.
    AMBIENCE_CHANNEL = 0
    FIRST_SFX_CHANNEL = 1

    def __init__(self, assets_path=None):
        """Initialize audio manager and load all sounds"""
        pygame.mixer.init()

        self.sounds = {}
        self.sfx_channels = {}  # name -> dedicated pygame.Channel
        self.master_volume = 0.2
        self.current_ambience = None

        self._load_all_sounds(assets_path or asset_dir())
        self._assign_channels()

        self.ambience_channel = pygame.mixer.Channel(self.AMBIENCE_CHANNEL)

    def stop_all(self):
        """Immediately cut all audio -- every SFX channel and ambience."""
        pygame.mixer.stop()
        self.current_ambience = None

    def _load_all_sounds(self, assets_path):
        sound_files = {
            # Ambience & music
            'ambience': 'sounds/ambience2.wav',
            'startup_theme': 'sounds/startup_theme.wav',

            # Ship movement & FTL / blink
            'thrust': 'sounds/thrust.wav',
            'ftl_jumping': 'sounds/ftl_jumping.wav',
            'ftl_arrival': 'sounds/ftl_arrival.wav',
            'blink': 'sounds/blink.wav',
            'blink_arrival': 'sounds/blink_arrival.wav',
            'inertial_dampener': 'sounds/inertial_dampener_toggle.wav',

            # Lasers
            'laser': 'sounds/laser_toggle.wav',
            'laser_dir_change': 'sounds/laser_dir_change.wav',
            'laser_warning': 'sounds/laser_warning.wav',
            'laser_locked': 'sounds/laser_locked.wav',
            'laser_turn_off': 'sounds/laser_turn_off.wav',
            'laser_lock_lost': 'sounds/laser_lock_lost.mp3',
            'material_scan' : 'sounds/material_scanner.wav',
            'material_scan_complete' : 'sounds/material_scan_complete.wav',
            'scan_interrupt' : 'sounds/scan_interrupt.wav',
            'mining_laser' : 'sounds/mining_laser.wav',

            # DFS scanner
            'dfs_toggle': 'sounds/dfs_toggle.wav',
            'dfs_scan': 'sounds/dfs_scan.wav',
            'dfs_dir_change': 'sounds/dfs_dir_change.mp3',
            'dfs_scan_warning': 'sounds/dfs_scan_warning.wav',

            # Missiles, radar & combat
            'fire_missile': 'sounds/fire_missile.wav',
            'enemy_missile_lock': 'sounds/enemy_missile_lock.wav',
            'missile_contact': 'sounds/missile_contact.wav',
            'deploy_decoy': 'sounds/deploy_decoy.wav',
            'radar': 'sounds/radar.wav',

            # Map & map markers
            'map_open': 'sounds/map_open.wav',
            'map_close': 'sounds/map_close.wav',
            'map_marker': 'sounds/map_marker.wav',
            'map_marker_place': 'sounds/map_marker_place.wav',
            'map_marker_delete': 'sounds/map_marker_delete.wav',

            # Warnings, damage & death
            # "Static Burst 2" by Silverillusionist for Asteroid Damage sfx
            'catastrophic_warning': 'sounds/catastrophic_warning.mp3',
            'pirate_warning': 'sounds/pirate_warning.wav',
            'damage_taken': 'sounds/damage_taken.wav',
            'asteroid_damage': 'sounds/asteroid_damage.wav',
            'low_health': 'sounds/low_health.wav',
            'death_screen': 'sounds/death_screen.wav',
            'low_fuel': 'sounds/low_fuel.wav',
            'blink_denied' : 'sounds/blink_denied.wav',

            # UI
            # "Glitch (Faulty Core) 9" by Dylan Kelk/SilverIllusionist for fuel acknowledge
            'retro_beep': 'sounds/retro_beep.wav',
            'close_range_toggle': 'sounds/close_range_toggle.wav',
            'cancel': 'sounds/cancel.wav',
            'typing_click': 'sounds/typing_click.wav',
            'pause' : 'sounds/pause.wav',
            'resume' : 'sounds/resume.wav',
            'shutdown' : 'sounds/shutdown.wav',
            'fuel_fault_acknowledge' : 'sounds/fuel_fault_acknowledge.wav',

            # Misc
            'keyboard_clack': 'sounds/keyboard_clack.wav',
            'startup' : 'sounds/startup.wav',
        }

        for name, filename in sound_files.items():
            filepath = os.path.join(assets_path, filename)
            try:
                sound = pygame.mixer.Sound(filepath)
                sound.set_volume(self.master_volume)
                self.sounds[name] = sound
            except Exception as e:
                print(f"[AUDIO ERROR] Failed to load {filename}: {e}")

    def _assign_channels(self):
        """Give every SFX its own dedicated channel so multiple distinct
        sounds can play simultaneously without overwriting each other."""
        sfx_names = [n for n in self.sounds if n != 'ambience']

        # One channel per SFX, plus the reserved ambience channel.
        needed = self.FIRST_SFX_CHANNEL + len(sfx_names)
        if pygame.mixer.get_num_channels() < needed:
            pygame.mixer.set_num_channels(needed)

        for i, name in enumerate(sfx_names):
            self.sfx_channels[name] = pygame.mixer.Channel(self.FIRST_SFX_CHANNEL + i)

    def play_sfx(self, name, force=False, loops=0, volume=1.0):
        channel = self.sfx_channels.get(name)
        if channel is None:
            print(f"[AUDIO] Sound not found: {name}")
            return

        # Same sound already playing -> leave it alone.
        if not force and channel.get_busy():
            return

        channel.set_volume(volume)
        channel.play(self.sounds[name], loops=loops)

    def set_sfx_volume(self, name, volume):
        """Change the volume of a sound that is already playing."""
        channel = self.sfx_channels.get(name)
        if channel is not None:
            channel.set_volume(volume)

    def stop_sfx(self, name):
        """Stop one specific sound effect (only its own channel)."""
        channel = self.sfx_channels.get(name)
        if channel is not None:
            channel.stop()

    def is_playing(self, name):
        """True if this specific sound is currently playing."""
        channel = self.sfx_channels.get(name)
        return channel.get_busy() if channel is not None else False

    def play_ambience(self, name, loops=-1):
        if name not in self.sounds:
            print(f"[AUDIO] Sound not found: {name}")
            return

        self.ambience_channel.stop()
        self.current_ambience = name
        self.ambience_channel.play(self.sounds[name], loops=loops)

    def stop_ambience(self):
        self.ambience_channel.stop()
        self.current_ambience = None

    def set_master_volume(self, volume):
        self.master_volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.master_volume)
