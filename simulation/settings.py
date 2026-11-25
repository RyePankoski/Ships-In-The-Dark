"""The world parameters a host chooses in the lobby: how big the world is, how many rocks
and where they sit, and how many drones and pirates are out there.

Every value is one of a short list of presets, so the lobby can cycle through them with
a click and the server can reject anything else. The settings travel with the server's
state, so every pilot builds the same world from them and the same seed.
"""
from dataclasses import dataclass, asdict, replace

# The choices for each setting, first one is the default. The lobby cycles through these in order.
OPTIONS = {
    'size': (1000, 3000, 5000, 8000, 10000, 12000, 20000),  # side length of the square world, world units
    'asteroids': (0, 10, 50, 100, 200, 500, 1000),  # rocks in the world
    'layout': ('scattered', 'clustered'),  # scattered: spread evenly; clustered: in belts
    'drones': (0, 2, 5, 10, 20, 40, 100),  # mining drones
    'pirates': (0, 1, 2, 3, 4, 5),  # mining vessels that shoot at pilots
}

LAYOUT_NAMES = {'scattered': 'SCATTERED', 'clustered': 'CLUSTERED'}


@dataclass(frozen=True)
class WorldSettings:
    size: int = OPTIONS['size'][3]
    asteroids: int = OPTIONS['asteroids'][3]
    layout: str = OPTIONS['layout'][0]
    drones: int = OPTIONS['drones'][2]
    pirates: int = OPTIONS['pirates'][0]

    def cycled(self, name):
        """The same settings with one of them moved to the next option (wrapping round)."""
        choices = OPTIONS[name]
        current = getattr(self, name)
        index = choices.index(current) if current in choices else -1
        return replace(self, **{name: choices[(index + 1) % len(choices)]})

    def to_wire(self):
        return asdict(self)

    @classmethod
    def from_wire(cls, data):
        """Settings from a dict off the network. Anything missing or not an option falls back to the default."""
        values = {}
        for name in OPTIONS:
            value = data.get(name) if isinstance(data, dict) else None
            if value in OPTIONS[name]:
                values[name] = value
        return cls(**values)

    def summary(self):
        return (f"WORLD {self.size} X {self.size}  //  {self.asteroids} ROCKS ({LAYOUT_NAMES[self.layout]})"
                f"  //  {self.drones} DRONES  //  {self.pirates} PIRATES")
