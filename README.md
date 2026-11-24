This is a python project built with pygame and the socket library. 

<img width="2559" height="1436" alt="Screenshot 2026-11-24 154615" src="https://github.com/user-attachments/assets/106ffb5a-a820-4ff8-af7a-44b7e50d503d" />

This is Ships in the Dark. It is functionally a submarine hunting game. You and your friends are remote piloting drones, and are hunting each-other. Your drones are equipped with various equipment and systems, like radar, long range scanners, mining lasers, material scanners, and more. The idea is that you are trying to find your opponent before they find you, then launch a missile at them to destroy them. 

However, taking damage or running low on fuel isn't the end. You can fly around the map and mine asteroids to repair your hull, refill your fuel, or resupply on missiles. 

The game works in multiplayer and all current functionality is multiplayer complete. The game has a lobby screen, a comprehensive profanity filter for the optional call-sign editor, local simulation and a lerp function.

## Features

### Game modes
- **Single player:** a practice hunt against one slow-drifting target that doesn't shoot back
- **Multiplayer:** host or join by IP address, up to 16 pilots (UDP port 27015)
- **Tutorial:** work in progress; currently an empty practice world with a welcome banner
- **Spectating:** after your ship is destroyed in multiplayer, watch the surviving pilots

### Menus and multiplayer lobby
- Animated boot screen and main menu, usable by keyboard or mouse
- Custom callsigns (up to 20 characters, profanity filtered), with a random one to start
- Lobby with pilot roster; the host launches the match and can return everyone to the lobby
- Pilots can join a match already in progress
- Host-adjustable world settings:

<img width="2559" height="1438" alt="Screenshot 2026-11-24 154629" src="https://github.com/user-attachments/assets/507e19f3-581b-43e6-81dc-be2a72dfbd17" />


| Setting | Options (default in bold) |
|---|---|
| World size | 1000, 3000, 5000, **8000**, 10000, 12000, 20000 |
| Asteroids | 0, 10, **50**, 100, 200, 500, 1000 |
| Asteroid layout | **Scattered**, clustered |
| Mining drones | 0, 2, **5**, 10, 20, 40 |
| Pirates | **0**, 1, 2, 3, 4, 5 |

- In-game operator console (Esc) with controls reference, manual and quit. It does not pause the game.

### Flight
- Momentum-based flight: thrust, reverse thrust, turning, sideways strafing and brakes
- Wider turns at higher speed
- Inertial dampener: slows the ship while coasting, or switch it off to drift freely
- **Blink drive:** after a 5.5 second charge, jumps you to a random point in the world. Breaks laser locks, needs more than 50 fuel, and burns a lot of it.
- Navigation readout (position, grid square, velocity, speed, heading) and optional on-screen heading/velocity arrows

<img width="2555" height="1438" alt="Screenshot 2026-11-24 154651" src="https://github.com/user-attachments/assets/59509274-6fdd-41af-baa6-b7002e48610e" />


### Sensors and instruments
- **Radar:** a 360° sweep that plots solid objects. It cannot see behind them, and returns from your laser target are highlighted.
- **Range bands:** radar rings that light up where ships, missiles, drones or pirates are moving, showing distance but not direction
- **Proximity scan:** low-power short-range sensor (on by default) that reveals nearby ships and feeds the tactical map
- **Deep field scanner (DFS):** aim in one of eight directions to detect moving ships or decoys at long range. The distance is only an estimate (up to 40% off), and ships you scan are warned.
- **DFS alert:** warns you when someone sweeps you; can be switched off
- **Laser assessor:** aim with the arrow keys or mouse, identify contacts as static or moving, and lock on. Enemies are warned when your beam touches them.
- **Material assessor:** analyzes whatever your laser is touching. It identifies enemy ships and asteroid types; farther targets take longer.
- **Tactical map:** nearby contacts with movement indicators, fading once out of range, plus your own markers in five shapes

### Weapons and countermeasures
- **Missiles:** 5 carried, 5 second reload. Put your laser on a target and fire; they home in and steer around asteroids. Firing switches the laser off.
- A missile hit takes 90 of your 100 hull and destroys most other things
- **Missile interception:** shoot down an incoming missile by targeting it with your laser and firing your own
- **Decoys:** drifting dummies lasting 30 seconds that can fool radar and the DFS. The material assessor shows them only as metallic.




### Fuel, power and stealth
- Every active system draws power, and draw burns fuel
- The more power you draw, the more visible your ship appears: at zero draw it cannot be seen in the flight window. Active sensors such as radar can still find it.
- Low fuel (below 20%) and high draw warnings
- An empty tank throttles your top speed and leaves you unable to blink

| System | Power draw |
|---|---|
| Blink drive (while charging) | 50 |
| Mining laser (while cutting) | 5 |
| Thrusters | 2 |
| Laser assessor | 1 |
| Deep field scanner | 1 |
| Inertial dampener | 1 |
| Turning, braking, material scan | 0.5 each |
| Radar sweep, range bands | 0.25 each |
| Proximity scan | 0.1 |
| DFS alert | 0.05 |

### Mining
Switch on the mining laser near a suitable asteroid. It takes 8 seconds to consume the rock.

<img width="2557" height="1439" alt="Screenshot 2026-11-24 154939" src="https://github.com/user-attachments/assets/aa204d9c-5bbd-43d1-ac94-0c6937b11db5" />


| Asteroid | Reward |
|---|---|
| Icy | 100 fuel (tank holds 401) |
| Metallic (rare) | 1 missile |
| Semi-metallic | Full hull repair |
| Rocky (most common) | Nothing |

### The world and its hazards
- Randomly generated asteroid fields, each rock with its own shape and designation
- Hitting an asteroid costs 50 hull
- **Mining drones:** harmless traffic that travels between asteroids and shows up on sensors
- **Pirates:** armed mining vessels that open fire on any pilot who comes close
- Below 20 hull your speed is limited while the hull slowly recovers to 20

### Warnings and feedback
- Alerts for laser contact, incoming missiles, imminent impact, DFS sweeps, pirate fire, low fuel and critical hull
- Hit confirmation and ship destruction notices
- Fault acknowledge button to silence the low fuel alarm

<img width="2549" height="1437" alt="Screenshot 2026-11-24 154725" src="https://github.com/user-attachments/assets/5e7d1008-0225-435d-b647-26074afa2f08" />

### Audio and visuals
- Sound effects for instruments, weapons, warnings, damage and menus, plus background ambience
- Retro CRT cockpit: scanlines, glow, static and flicker, with screen tearing as your hull takes damage (F9 toggles)
- Worn instrument panels, explosions and weapon effects



### Controls

<img width="2559" height="1439" alt="Screenshot 2026-11-24 154856" src="https://github.com/user-attachments/assets/77f687b9-7f4e-40a0-9808-41dfccb23a58" />


| Key | Action |
|---|---|
| W / S | Thrust / reverse |
| A / D | Turn |
| Shift + A / D | Strafe |
| Tab (hold) | Brake |
| G | Inertial dampener |
| T | Blink drive |
| I | Laser on/off |
| Left / Right, or hold left click | Aim laser |
| Space | Lock / release laser |
| N | Material scan |
| P | Fire missile |
| Right Alt | Deploy decoy |
| E | Mining laser |
| R | Radar sweep |
| L | Range bands |
| Q | Proximity scan |
| K | DFS on/off |
| Up / Down | DFS direction |
| O | Run DFS scan |
| M | Tactical map |
| H | Heading / velocity arrows |
| F9 | CRT filter |
| Esc | Close map / open console |

<img width="2559" height="1439" alt="Screenshot 2026-08-01 191949" src="https://github.com/user-attachments/assets/5b72b209-31ac-4d2e-9ee0-6a5a08359d70" />
