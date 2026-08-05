class Asteroid:
    def __init__(self, x, y, size):
        self.pos_x = x
        self.pos_y = y
        self.size = size
        self.painted = False
        self.radar_cross_section = self.size

        self.player_id = 0
        self.alive = True