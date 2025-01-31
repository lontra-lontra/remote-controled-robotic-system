import io
import logging
import json
from threading import Thread
from flask import Flask, Response, request, jsonify, render_template
import os
from our_socket_module import WebSocketClient  # Import the WebSocketClient module
import cv2
import time
from picamera2 import Picamera2
import numpy as np


time_zero = time.time()


centre = (402, 271)
plus_loing = (577, 319)
plus_proche = (232, 252)







frame = None
should_stop = False

def create_mask(image):
    """Applique un masque basé sur des seuils HSV et retourne le masque binaire."""
    # Convertir l'image en BGR -> HSV
    image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Définir les seuils pour chaque canal HSV
    lower_bound = np.array([0.587 * 180, 0.415 * 255, 0.284 * 255], dtype=np.uint8)
    upper_bound = np.array([0.740 * 180, 1.000 * 255, 0.827 * 255], dtype=np.uint8)
    
    # Créer le masque binaire
    mask = cv2.inRange(image_hsv, lower_bound, upper_bound)
    return mask

def find_centroid_of_largest_contour(mask):
    """Trouve le centroïde du plus grand contour dans l'image binaire."""
    # Trouver les contours dans l'image binaire
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # Trouver le plus grand contour par aire
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Calculer le centroïde du plus grand contour
        moments = cv2.moments(largest_contour)
        if moments["m00"] != 0:
            # Calcul du centroïde (cx, cy)
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
            return (cx, cy)
    return None

def process_frame(frame):
    """Traite une frame et retourne le masque et le centroïde."""
    # Convertir de RGB à BGR pour OpenCV
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    frame_bgr = cv2.flip(frame_bgr,0)
    
    # Créer le masque
    mask = create_mask(frame_bgr)
    
    # Trouver le centroïde
    centroid = find_centroid_of_largest_contour(mask)
    
    # Dessiner le centroïde sur la frame si trouvé
    if centroid is not None:
        cv2.circle(frame_bgr, centroid, 5, (0, 255, 0), -1)
        
    return frame_bgr, mask, centroid

def generate_frames():
    global frame, should_stop
    
    # Initialize the camera
    picam2 = Picamera2()
    
    # Configure camera
    config = picam2.create_preview_configuration(
        main={"size": (640, 480)},
        buffer_count=2
    )
    picam2.configure(config)
    
    # Start the camera
    picam2.start()
    
    # Allow camera to warm up
    time.sleep(2)
    
    while not should_stop:
        capture_time = time.time() - time_zero
        
        # Capture frame (en RGB)
        frame = picam2.capture_array()
        
        # Traiter l'image
        processed_frame, mask, centroid = process_frame(frame)
        
        if centroid is not None:
            print("centroid", centroid)
        
        # Convert frame to jpg for streaming
        ret, buffer = cv2.imencode('.jpg', processed_frame)
        frame_bytes = buffer.tobytes()
        


        sign = np.sign(centroid[0] - centre[0]) 
        distance = np.linalg.norm(np.array(centroid) - np.array(centre))

        scale = 0.1/np.linalg.norm(np.array(plus_loing) - np.array(plus_proche))
        
        distance = distance * scale * sign
        last_10_received_values.append([distance, capture_time])
        print("scale", scale)


        if len(last_10_received_values) > 100:
            last_10_received_values.pop(0)
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


    
    # Cleanup
    picam2.stop()





















# Read configuration from config.json]
# Deduce the path to the config file
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, 'config.json')
with open(config_path) as config_file:
    config = json.load(config_file)



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




if config["camera"]:
    @app.route('/video_feed')
    def video_feed():
        return Response(generate_frames(),
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

@app.route('/')
def index():
    return render_template('test.html')


@app.route('/graph')
def g():
    return render_template('g.html')

@app.route('/values', methods=['GET'])
def l():
    last_10_received_values_minus_2 = [[x[0]-2,x[1]] for x in last_10_received_values]
    return jsonify(last_10_received_values_minus_2)


@app.route('/values_camera', methods=['GET'])
def l_camera():
    return jsonify(last_10_received_values)



# Route for sending data over WebSocket
@app.route('/api/send-data', methods=['POST'])
def send_data():
    global time_zero 
    time_zero = time.time()
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
