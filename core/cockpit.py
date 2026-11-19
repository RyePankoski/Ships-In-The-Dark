class Cockpit:
    """What *this* player has switched on and what their instruments show.

    This is client-only state: it is never sent over the network and the server
    never sees it. The ship itself (position, health, missiles...) is a fact about
    the world and lives on objects.ship.Ship.
    """

    def __init__(self):
        # Switches
        self.close_range_scanning = True
        self.dfs_on = False
        self.laser_on = False
        self.manual_control = True

        # Targeting: the object the laser is locked on (a world object or None)
        self.target = None
        self.has_missile_solution = False

        # Threat warnings, worked out each frame from the world
        self.enemy_has_missile_solution = False
        self.catastrophic_warning = False
        self.dfs_scanned = False

        # Instrument readouts
        self.deep_field_contacts = []
        self.unconfirmed_signatures = []
        self.confirmed_signatures = []
