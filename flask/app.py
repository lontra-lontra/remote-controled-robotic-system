
import json
from threading import Thread
from flask import Flask, Response, request, jsonify, render_template
import os
import cv2
import time
from picamera2 import Picamera2
import numpy as np
import RPi.GPIO as GPIO
from flask.socket_module import WebSocketClient
from flask.image_processing import generate_frames

time_zero = time.time()


buffer_size = 100


# Read configuration from config.json]
# Deduce the path to the config file
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, 'config.json')
config_file = open(config_path)
config = json.load(config_file)
config_file.close()

print(config)
WEBSOCKET_URL = f"ws://{config['matlab_socket_Server_IP_Adress']}:{config['matlab_socket_Server_Port']}"
values = []
values_vitesse = []
values_sensor =[]
values_sensor_vitesse =[]
values_motor =[]

if config["camera"]:
    picam2 = Picamera2()

    

    # Configurer la caméra avec l’image complète et prévisualisation 640x480
    picam2.configure(
        picam2.create_preview_configuration(
        main={"size": (640, 480)},
        buffer_count=2
    )
    )
    # Allow camera to warm up
    time.sleep(2)

    picam2.start()
    


frame = None
should_stop = False








app = Flask(__name__)

# WebSocket settings


# WebSocket message handler
def handle_websocket_message(message):
    arduino_time = message["Signal"][0]["Value"][0]
    value = message["Signal"][1]["Value"][0]
    motor_value = message["Signal"][2]["Value"][0]
    print("arduino_time:"+ str(arduino_time))
    


    global values_sensor
    values_sensor.append([value, arduino_time])
    if len(values_sensor) > buffer_size:
        values_sensor.pop(0)

    global values_motor
    values_motor.append([motor_value-90, arduino_time])
    if len(values_motor) > buffer_size:
        values_motor.pop(0)
# Create WebSocketClient instance
websocket_client = WebSocketClient(on_message=handle_websocket_message)


if config["camera"]:
    @app.route('/video_feed')
    def video_feed():
        return Response(generate_frames(values),
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

#@app.route('/ancien')
#%def index_ancien():
#    return render_template('test.html')

@app.route('/')
def index_new():
    return render_template('final.html')

#@app.route('/')
#def index():
#    return render_template('test.html')


@app.route('/graph')
def g():
    return render_template('graph.html')

@app.route('/graphgraph')
def gg():
    return render_template('graphgraph.html')

@app.route('/values', methods=['GET'])
def l():
    return jsonify(values_sensor)

@app.route('/values_camera', methods=['GET'])
def l_camera():
    return jsonify(values)

def low_pass_filter(values, alpha=0.1):
    """Applique un filtre passe-bas sur les valeurs."""
    if not values:
        return []

    filtered_values = [values[0]]  # Initialize with the first value
    for i in range(1, len(values)):
        previous_filtered_value = filtered_values[-1][0]
        current_value = values[i][0]
        current_time = values[i][1]
        new_filtered_value = alpha * current_value + (1 - alpha) * previous_filtered_value
        filtered_values.append([new_filtered_value, current_time])

    return filtered_values

@app.route('/values_camera_filtered', methods=['GET'])
def f_values_camera_filtered():
    values_camera_filtered = low_pass_filter(values)
    return jsonify(values_camera_filtered)


@app.route('/control', methods=['GET'])
def f_control():
    values_camera_filtered = low_pass_filter(values)
    return render_template('control.html')



@app.route('/values_derivative_of_camera_filtered', methods=['GET'])
def f_values_derivative_of_camera_filtered():
    if len(values) > 1:
        values_array = np.array(values)
        distances = values_array[:, 0]
        times = values_array[:, 1]
        derivatives = np.diff(distances) / np.diff(times)
        times = times[1:]  # Adjust times array to match the length of derivatives
        values_derivative_of_camera_filtered = list(zip(derivatives, times))
    else:
        values_derivative_of_camera_filtered = []
    return jsonify(values_derivative_of_camera_filtered)


@app.route('/values_speed_camera', methods=['GET'])
def l_speed_camera():
    # Calculate the gradient of the values
    if len(values) > 1:
        values_array = np.array(values)
        distances = values_array[:, 0]
        times = values_array[:, 1]
        gradients = np.gradient(distances, times)
        values_vitesse = list(zip(gradients, times))
    else:
        values_vitesse = []

    return jsonify(values_vitesse)


@app.route('/values_motor', methods=['GET'])
def l_motor():
    return jsonify(values_motor)

@app.route('/reset', methods=['POST'])
def reset():
    reset_timer()
    reset_values()
    return jsonify({"message": "Timer and values reset successfully"}), 200





def reset_timer():
    # Set up GPIO
    global time_zero 
    
    time_zero = time.time() # reset the time to zero
                            # reset arduino time to zero
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.OUT)
    # Set GPIO2 high
    GPIO.output(17, GPIO.HIGH)
    time.sleep(0.1)
    # Set GPIO2 low
    GPIO.output(17, GPIO.LOW)

    # Clean up GPIO
    #GPIO.cleanup()

def reset_values():
    global values
    global values_vitesse   
    global values_sensor
    global values_motor
    global values_sensor_vitesse
    values = []
    values_vitesse = []
    values_sensor = []
    values_sensor_vitesse = []
    values_motor = []


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
    app.run(host='0.0.0.0', port=1981, debug=False)
