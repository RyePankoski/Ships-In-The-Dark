ASTEROID PATTERN GENERATION:
Return to the asteroid generation. The idea to make curvy asteroid belts is this:
Subdivide the line between start and end. Pull those points up and down perpendicular to the line by random amounts.
Then generate the points between those lines, creating an overall wavy line.
Also, pick the subdivisions randomly with some sort of clamp on minimum distance and max distance. 

MISSILE PLAN:
The missiles are goofy. They are great at avoiding asteroids, but they need a max turn rate, and turning with no fuel should cost them energy, such that they slow down. 
I know this is an aerodynamic missile property, so we can justify it by saying the rocket has little rcs thrusters or something. They will need drastically more fuel, and a max
speed. This should make it possible to hide from missiles by going behind a rock. 
