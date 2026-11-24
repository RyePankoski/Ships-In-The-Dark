class TacticalMapState:
    """What the tactical map shows: whether it is open, the markers the pilot has
    placed, and where a marker placement is in progress.

    Local to this client; markers are never sent to the server. The scene plays the
    sounds, this class only keeps the state and its transitions.
    """

    def __init__(self):
        self.is_open = False
        # (shape, world_x, world_y)
        self.markers = []
        # None, 'PICK' (choosing a shape) or a shape name (the next map click places it)
        self.marker_mode = None

    @property
    def placing(self):
        return self.marker_mode is not None

    def toggle(self):
        self.is_open = not self.is_open
        self.marker_mode = None

    def close(self):
        self.is_open = False

    def start_marker(self):
        self.marker_mode = 'PICK'

    def choose_shape(self, shape):
        self.marker_mode = shape.upper()

    def cancel_marker(self):
        self.marker_mode = None

    def place(self, marker):
        """Add the marker from a click. Returns False (and changes nothing) if there is none."""
        if marker is None:
            return False
        self.markers.append(marker)
        self.marker_mode = None
        return True

    def clear_markers(self):
        self.markers.clear()
