import pygame
import os


class AudioManager:
    def __init__(self, assets_path='assets'):
        pygame.mixer.init()
        self.sounds = {}
        self.ambience_channel = pygame.mixer.Channel(0)
        self.current_ambience = None
        self.master_volume = 0.05

        self._load_all_sounds(assets_path)

    def _load_all_sounds(self, assets_path):
        sound_files = {
            'ambience': 'sounds/ambience.mp3',
        }

        for name, filename in sound_files.items():
            filepath = os.path.join(assets_path, filename)
            try:
                self.sounds[name] = pygame.mixer.Sound(filepath)
                self.sounds[name].set_volume(self.master_volume)
                print(f"[AUDIO] Loaded: {name}")
            except Exception as e:
                print(f"[AUDIO ERROR] Failed to load {filename}: {e}")

    def play_sfx(self, name):
        if name in self.sounds:
            self.sounds[name].play()
        else:
            print(f"[AUDIO] Sound not found: {name}")

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