import io
import logging
import json
from threading import Thread
from flask import Flask, Response, request, jsonify, render_template
import os
from our_socket_module import WebSocketClient  # Import the WebSocketClient module

# Read configuration from config.json]
# Deduce the path to the config file
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

# Camera setup
if config["camera"]:
    from picamera2 import Picamera2
    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
    picam2.start()

app = Flask(__name__)

# WebSocket settings
WEBSOCKET_URL = f"ws://{config['matlab_socket_Server_IP_Adress']}:{config['matlab_socket_Server_Port']}"
last_10_received_values = []

# WebSocket message handler
def handle_websocket_message(message):
    value = message["Signal"][0]["Value"][0]
    global last_10_received_values
    last_10_received_values.append(value)
    if len(last_10_received_values) > 100:
        last_10_received_values.pop(0)

# Create WebSocketClient instance
websocket_client = WebSocketClient(on_message=handle_websocket_message)

from flask import Flask, Response, render_template_string, request
import io
import threading
import time
import cv2
import os

from flask import Flask, Response, render_template_string, request
from picamera2 import Picamera2
import io
import threading
import time
from collections import deque

app = Flask(__name__)

# Settings
FRAME_BUFFER_SIZE = 300  # Number of frames to keep in buffer (e.g., 10 seconds at 30 FPS)
FPS = 30  # Frames per second
buffer = deque(maxlen=FRAME_BUFFER_SIZE)  # Circular buffer for frames
lock = threading.Lock()

# Initialize Picamera2
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

# Function to capture frames
def capture_frames():
    global buffer
    while True:
        output = io.BytesIO()
        picam2.capture_file(output, format='jpeg')
        with lock:
            buffer.append(output.getvalue())
        time.sleep(1 / FPS)

# Route to serve video stream
@app.route('/video_feed')
def video_feed():
    start_index = int(request.args.get("start", 0))
    while True:
        with lock:
            if start_index < len(buffer):
                frame = buffer[start_index]
                start_index += 1
            else:
                time.sleep(0.1)
                continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# HTML route
@app.route('/camera_view')
def camera_view():
    return render_template_string("""
    <html>
    <body>
        <video id="videoPlayer" controls autoplay>
            <source src="/video_feed" type="multipart/x-mixed-replace; boundary=frame">
        </video>
        <script>
            const player = document.getElementById('videoPlayer');
            player.addEventListener('seeked', function () {
                const position = Math.round(player.currentTime * {{ fps }});
                player.src = '/video_feed?start=' + position;
                player.play();
            });
        </script>
    </body>
    </html>
    """, fps=FPS)

if __name__ == '__main__':
    threading.Thread(target=capture_frames, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)


if __name__ == '__main__':
    threading.Thread(target=capture_frames, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)


@app.route('/')
def index():
    return render_template('test.html')


@app.route('/graph')
def g():
    return render_template('g.html')

@app.route('/values', methods=['GET'])
def l():
    return jsonify(last_10_received_values)



# Route for sending data over WebSocket
@app.route('/api/send-data', methods=['POST'])
def send_data():
    """Send data to WebSocket server."""
    try:
        data = request.json
        websocket_client.send_message(data)
        return jsonify({"message": "Data sent successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start Flask app
    app.run(host='0.0.0.0', port=1981)
