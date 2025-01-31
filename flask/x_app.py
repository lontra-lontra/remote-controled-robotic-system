import io
import json
import os
from flask import Flask, Response, request, jsonify, render_template
from websocket_client import websocket_client
from camera import gen_frames

# Read configuration from config.json
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)

app = Flask(__name__)
last_10_received_values = []


from our_socket_module import WebSocketClient

last_10_received_values = []

def handle_websocket_message(message):
    value = message["Signal"][0]["Value"][0]
    global last_10_received_values
    last_10_received_values.append(value)
    if len(last_10_received_values) > 100:
        last_10_received_values.pop(0)

# Create WebSocketClient instance
websocket_client = WebSocketClient(on_message=handle_websocket_message)


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/camera_view')
def camera_view():
    return """
    <html>
    <body>
    <img src="/video_feed">
    </body>
    </html>
    """

@app.route('/')
def index():
    return render_template('test.html')

@app.route('/graph')
def g():
    return render_template('g.html')

@app.route('/values', methods=['GET'])
def l():
    return jsonify(last_10_received_values)

@app.route('/api/send-data', methods=['POST'])
def send_data():
    try:
        data = request.json
        websocket_client.send_message(data)
        return jsonify({"message": "Data sent successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1981)
