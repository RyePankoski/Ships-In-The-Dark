import pygame
import os


class AudioManager:
    # Channel 0 is reserved for looping ambience. Each SFX gets its own
    # dedicated channel starting from FIRST_SFX_CHANNEL, so distinct sounds
    # never share a channel (they can all play at once) and "is this sound
    # already playing?" is just that channel's busy state.
    AMBIENCE_CHANNEL = 0
    FIRST_SFX_CHANNEL = 1

    def __init__(self, assets_path='assets'):
        """Initialize audio manager and load all sounds"""
        pygame.mixer.init()

        self.sounds = {}
        self.sfx_channels = {}  # name -> dedicated pygame.Channel
        self.master_volume = 0.2
        self.current_ambience = None

        self._load_all_sounds(assets_path)
        self._assign_channels()

        self.ambience_channel = pygame.mixer.Channel(self.AMBIENCE_CHANNEL)

    def stop_all(self):
        """Immediately cut all audio -- every SFX channel and ambience."""
        pygame.mixer.stop()
        self.current_ambience = None

    def _load_all_sounds(self, assets_path):
        sound_files = {
            'ambience': 'sounds/ambience.mp3',
            'retro_beep': 'sounds/retro_beep.wav',
            'thrust': 'sounds/thrust.wav',
            'enemy_missile_lock': 'sounds/enemy_missile_lock.wav',
            'radar': 'sounds/radar.mp3',
            'death_screen': 'sounds/death_screen.wav',
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

    def play_sfx(self, name, force=False):
        """Play a sound effect on its own dedicated channel.

        If this same sound is already playing, it is left running (so calling
        this every frame won't restart it). Pass force=True to restart it from
        the beginning. Different sounds are on different channels, so any number
        of them can play at the same time.

        Args:
            name: Sound identifier
            force: If True, restart this sound even if it's already playing
        """
        channel = self.sfx_channels.get(name)
        if channel is None:
            print(f"[AUDIO] Sound not found: {name}")
            return

        # Same sound already playing -> leave it alone.
        if not force and channel.get_busy():
            return

        channel.play(self.sounds[name])

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
