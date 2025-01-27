import asyncio
import websockets
import logging
import json
from threading import Thread
import os
import time

# Configuration
config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path, 'r') as config_file:
    config = json.load(config_file)

SERVER_IP = config["matlab_socket_Server_IP_Adress"]
SERVER_PORT = config["matlab_socket_Server_Port"]

WEBSOCKET_URL = f"ws://{SERVER_IP}:{SERVER_PORT}"

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class WebSocketClient:
    def __init__(self, on_message=lambda x: None):
        self.websocket = None
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        self.connection_ready = False
        self.last_values = [] 
        self.on_message = on_message

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect_and_listen())

    async def _connect_and_listen(self):
        try:
            async with websockets.connect(WEBSOCKET_URL) as self.websocket:
                self.connection_ready = True
                logging.info(f"Connected to WebSocket server at {WEBSOCKET_URL}")
                while True:
                    try:
                        response = await self.websocket.recv()
                        response = json.loads(response)
                        self.on_message(response)
                        #self.last_values.append(response["Signal"][0]["Value"])
                        ##if len(self.last_values) > 10:
                        #   self.last_values.pop(0)
                        
                        
                    except websockets.ConnectionClosed:
                        logging.warning("Connection closed by the server.")
                        break
        except Exception as e:
            logging.error(f"Failed to connect to WebSocket server: {e}")

    def send_message(self, message, timeout=5):
        if not self.connection_ready:
            logging.error("WebSocket connection is not ready.")
            return
        
        async def _send():
            if self.websocket:
                #logging.info(f"Message being to server: {message}")
                await self.websocket.send(json.dumps(message))
                logging.info(f"Message sent to server: {message}")
            else:
                logging.error("WebSocket connection not established.")
        
        try:
            asyncio.run_coroutine_threadsafe(asyncio.wait_for(_send(), timeout), self.loop)
        except asyncio.TimeoutError:
            logging.error(f"Failed to send message within {timeout} seconds.")
        except Exception as e:
            logging.error(f"Error while sending message: {e}")

