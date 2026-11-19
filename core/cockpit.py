class Cockpit:
    """What *this* player is flying with that more than one thing cares about.

    This is client-only state: it is never sent over the network and the server
    never sees it. The ship itself (position, health, missiles...) is a fact about
    the world and lives on objects.ship.Ship. Each sensor keeps its own switch and
    readouts (see instruments/instrument.py).
    """

    def __init__(self):
        self.manual_control = True

        # Targeting: the object the laser is locked on (a world object or None)
        self.target = None
        self.has_missile_solution = False

        # Threat warnings, worked out each frame from the world
        self.enemy_has_missile_solution = False
        self.catastrophic_warning = False
        self.dfs_scanned = False
