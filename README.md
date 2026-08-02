This is a python project built with pygame and the socket library. 

It is about 2 players, who must rely entirely on their instruments, sensors, and electronic counter measures to find and eliminate the other player. 
If one player gets a weapon solution on the other, the missile they fire will not miss. The player being fired upon must use counter measures, hiding, or 
prayer to avoid the missile. 

There is not much to this project yet. I am trying to simplify the net-code and the gameplay considerably. I am also slowing the pace of the game down a lot
to avoid issues with de-sync and my inability to write rollback and sync code properly. Scope is everything. 

Some of the features I have added:

-It has working net-code, you can play with anyone around the world. Of course, you need to port forward and stuff, and there is nothing to do since I haven't finished updating the server to have
the same stuff as the main scene.
-There is a sonar scan, using ray-casting in a circle to create a useful instrument that doesn't spoof anything. 
-Missiles track and steer around asteroids.
-Many UI elements respond and new sound effects.

I will update this read-me as the project develops into something more real.


<img width="2559" height="1439" alt="Screenshot 2026-08-01 191949" src="https://github.com/user-attachments/assets/5b72b209-31ac-4d2e-9ee0-6a5a08359d70" />
