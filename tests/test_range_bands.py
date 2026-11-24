from instruments.range_bands import band_index
from objects.drone import Drone

RINGS, RANGE = 6, 600  # each band is 100 wide


def test_band_index_inside_bands():
    assert band_index(0, RINGS, RANGE) == 1  # zero distance is the innermost band
    assert band_index(99.9, RINGS, RANGE) == 1
    assert band_index(150, RINGS, RANGE) == 2
    assert band_index(599.9, RINGS, RANGE) == RINGS


def test_band_index_on_a_ring_belongs_to_the_outer_band():
    assert band_index(100, RINGS, RANGE) == 2
    assert band_index(500, RINGS, RANGE) == 6


def test_band_index_at_or_beyond_max_range_is_none():
    assert band_index(600, RINGS, RANGE) is None
    assert band_index(5000, RINGS, RANGE) is None


def test_drone_moving_follows_am_mining_not_stale_velocity():
    drone = Drone(0, 0)
    drone.vel_x = 50  # left over from the last leg of the flight
    assert drone.moving
    drone.am_mining = True
    assert not drone.moving


def test_drone_without_velocity_still_moves_when_not_mining():
    # A client's drone never receives a velocity
    drone = Drone(0, 0)
    assert drone.vel_x == 0 and drone.vel_y == 0
    assert drone.moving
