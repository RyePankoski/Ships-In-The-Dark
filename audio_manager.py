import pygame
import os


class AudioManager:
    def __init__(self, assets_path='assets'):
        """Initialize audio manager and load all sounds"""
        pygame.mixer.init()

        self.sounds = {}
        self.sound_channels = {}  # Track which channel each sound is on
        self.ambience_channel = pygame.mixer.Channel(0)
        self.current_ambience = None
        self.master_volume = 0.2

        self._load_all_sounds(assets_path)

    def _load_all_sounds(self, assets_path):
        sound_files = {
            'ambience': 'sounds/ambience.mp3',
            'retro_beep': 'sounds/retro_beep.wav',
            'thrust': 'sounds/thrust.wav',
            'enemy_missile_lock': 'sounds/enemy_missile_lock.wav',
        }

        for name, filename in sound_files.items():
            filepath = os.path.join(assets_path, filename)
            try:
                self.sounds[name] = pygame.mixer.Sound(filepath)
                self.sounds[name].set_volume(self.master_volume)

            except Exception as e:
                print(f"[AUDIO ERROR] Failed to load {filename}: {e}")

    def play_sfx(self, name, force=False):
        """Play a sound effect

        Args:
            name: Sound identifier
            force: If True, restart sound even if playing
        """
        if name not in self.sounds:
            print(f"[AUDIO] Sound not found: {name}")
            return

        # Get or create channel for this sound
        if name not in self.sound_channels:
            self.sound_channels[name] = pygame.mixer.find_channel()

        channel = self.sound_channels[name]

        # Check if already playing (unless force=True)
        if not force and channel.get_busy():
            return

        channel.play(self.sounds[name])

    def stop_sfx(self, name):
        if name in self.sounds:
            self.sounds[name].stop()

    def is_playing(self, name):
        """Check if a sound is currently playing"""
        if name in self.sound_channels:
            return self.sound_channels[name].get_busy()
        return False

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
