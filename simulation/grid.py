"""A spatial grid: objects bucketed by the GRID_SIZE cell they sit in.

The grid owns the bookkeeping. Callers add, remove and move objects; nobody
stores or updates a cell on the object itself, so the two can't drift apart.
Call `move` after an object's position changes and it is re-filed if needed.

An object is filed under the cell of its (pos_x, pos_y) at the time of the
last add or move. Each object must be in the grid at most once.
"""
import math

from config.constants import GRID_SIZE


class Grid:
    def __init__(self, cell_size=GRID_SIZE):
        self.cell_size = cell_size
        self._cells = {}   # (gx, gy) -> [objects in that cell]
        self._where = {}   # object -> the cell it is filed under

    def cell_of(self, x, y):
        return (int(x // self.cell_size), int(y // self.cell_size))

    def add_to_grid(self, obj):
        cell = self.cell_of(obj.pos_x, obj.pos_y)
        self._cells.setdefault(cell, []).append(obj)
        self._where[obj] = cell

    def remove(self, obj):
        cell = self._where.pop(obj)
        bucket = self._cells[cell]
        bucket.remove(obj)
        if not bucket:
            del self._cells[cell]

    def move(self, obj):
        """Re-file obj after its position changed. Cheap when it stayed in its cell."""
        if self.cell_of(obj.pos_x, obj.pos_y) != self._where[obj]:
            self.remove(obj)
            self.add_to_grid(obj)

    def clear(self):
        self._cells.clear()
        self._where.clear()

    def near(self, x, y, reach=0):
        """Objects in the cell containing (x, y) and the `reach` cells around it, as a list.
        A list rather than a generator: this runs many times a frame and most calls are small."""
        size = self.cell_size
        cx, cy = int(x // size), int(y // size)
        cells = self._cells
        found = []
        for gx in range(cx - reach, cx + reach + 1):
            for gy in range(cy - reach, cy + reach + 1):
                bucket = cells.get((gx, gy))
                if bucket:
                    found.extend(bucket)
        return found

    def reach_for(self, distance):
        """How many cells a search of `distance` has to look past its own cell."""
        return math.ceil(distance / self.cell_size)

    def __contains__(self, obj):
        return obj in self._where

    def __len__(self):
        return len(self._where)

    def __iter__(self):
        # A snapshot list, so callers may add/remove/move while looping over it.
        return iter([obj for bucket in self._cells.values() for obj in bucket])
