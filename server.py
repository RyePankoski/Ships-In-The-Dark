import json
from server_scene import ServerScene


class Server:
    def __init__(self, network_layer):
        self.network_layer = network_layer
        self.message_queue = []
        self.server_scene = ServerScene(connected_players=[])
        self.connected_players = set()
        self.current_frame_inputs = {}  # Buffer inputs this frame

    def run(self, dt):
        self.listen_for_messages()
        self.parse_messages()
        self.step_if_ready(dt)

        state = self.server_scene.get_state()
        serialized_state = self.serialize_state(state)
        self.send_to_all(json.dumps(serialized_state).encode())

    def serialize_state(self, state):
        serialized_ships = []
        for ship in state.get('player_ships', []):
            ship_dict = {
                'pos_x': ship.pos_x,
                'pos_y': ship.pos_y,
                'vel_x': ship.vel_x,
                'vel_y': ship.vel_y,
                'heading': ship.heading,
                'player_id': str(ship.player_id) if ship.player_id else None,
            }
            serialized_ships.append(ship_dict)

        return {
            'player_ships': serialized_ships
        }

    def send_to_all(self, serialized_state):
        for address in self.connected_players:
            # Add this player's ID to the state so they know which ship is theirs
            state_dict = json.loads(serialized_state.decode())
            state_dict['your_player_id'] = str(address)
            message = json.dumps(state_dict).encode()
            self.network_layer.send_to(message, address)

    def listen_for_messages(self):
        while True:
            message = self.network_layer.listen_for_messages()
            if message is not None:
                self.message_queue.append(message)
            else:
                break

    def parse_messages(self):
        for message in self.message_queue:
            if message is not None:
                data, address = message

                # New player connecting
                if address not in self.connected_players:
                    self.connected_players.add(address)
                    self.server_scene.connected_players.append(address)
                    self.server_scene.create_player_ships(address)
                    print(f"Player connected: {address}")
                try:
                    decoded = json.loads(data.decode())
                    self.current_frame_inputs[address] = decoded.get('input_data')
                except Exception as e:
                    print(f"Error parsing message: {e}")

        self.message_queue.clear()

    def step_if_ready(self, dt):
        # Check if we have inputs from ALL connected players
        if all(player_id in self.current_frame_inputs for player_id in self.server_scene.connected_players):
            messages = [
                {'player_id': player_id, 'input_data': self.current_frame_inputs[player_id]}
                for player_id in self.server_scene.connected_players
            ]
            self.server_scene.step(messages, dt)
            self.current_frame_inputs = {}  # Clear buffer for the next frame