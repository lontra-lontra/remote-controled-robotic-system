import io
import logging
import threading
import json
from flask import Flask, Response, request, jsonify
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
import websocket

app = Flask(__name__)

# Camera setup
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

# WebSocket settings
WEBSOCKET_URL = "ws://172.16.16.134:8080"
ws = None

    # Store the last 10 received values
last_10_received_values = []

def on_message(ws, message):
    print("Received message:", message)
    """Callback for when a message is received from the WebSocket."""
    global last_10_received_values
    data = json.loads(message)
    last_10_received_values.append(data)
    if len(last_10_received_values) > 10:
        last_10_received_values.pop(0)


def websocket_connect():
    """Connect to WebSocket server."""
    global ws
    try:
        ws = websocket.create_connection(WEBSOCKET_URL)
        print("Connected to WebSocket server")
        ws.on_message = on_message
    except Exception as e:
        print(f"Error connecting to WebSocket: {e}")

# Route for video streaming
def gen_frames():
    """Generate video frames from the camera."""
    output = io.BytesIO()
    while True:
        picam2.capture_file(output, format='jpeg')
        frame = output.getvalue()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        output.seek(0)
        output.truncate()

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/camera_view')
def camera_view():
    return """
    <html>
    <body>
    <img src="/video_feed">
    </body>
    </html>
    """

from flask import render_template

@app.route('/')
def index():
    return render_template('test.html')



        
@app.route('/l')
def l():
    return last_10_received_values.str()  


# Route for sending data over WebSocket
@app.route('/api/send-data', methods=['POST'])
def send_data():
    """Send data to WebSocket server."""
    global ws
    if ws is None or not ws.connected:
        websocket_connect()

    try:
        data = request.json
        if ws and ws.connected:
            ws.send(json.dumps(data))
            return jsonify({"message": "Data sent successfully"}), 200
        else:
            return jsonify({"error": "WebSocket is not connected"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start WebSocket connection in a separate thread
    websocket_thread = threading.Thread(target=websocket_connect)
    websocket_thread.daemon = True
    websocket_thread.start()

    # Start Flask app
    app.run(host='0.0.0.0', port=1981)
