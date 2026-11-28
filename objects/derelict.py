from objects.base import WorldObject

class Derelict(WorldObject):
    kind = 'derelict'
    material = 'advanced_composite'
    def __init__(self, x, y):
        self.pos_x = x
        self.pos_y = y
        pass