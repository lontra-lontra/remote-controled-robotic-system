import io
import threading
import json
from flask import Flask, Response, request, jsonify
from picamera2 import Picamera2
import cv2
import numpy as np
import websocket

# Setup Flask application
app = Flask(__name__)

# Camera setup
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

# WebSocket settings
WEBSOCKET_URL = "ws://172.16.16.134:8080"
ws = None

# Function to create mask
def create_mask(image_bytes):
    """Applique un masque basé sur des seuils HSV et retourne uniquement le masque binaire."""
    # Convertir les bytes en image OpenCV
    image_np = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    
    if image is None:
        print("Erreur : Impossible de charger l'image !")
        return None

    # Convertir l'image en BGR -> HSV
    image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Définir les seuils pour chaque canal HSV
    lower_bound = np.array([0.071 * 255, 0.721 * 255, 0.000 * 255], dtype=np.uint8)
    upper_bound = np.array([0.110 * 255, 0.898 * 255, 0.542 * 255], dtype=np.uint8)

    # Créer le masque binaire
    mask = cv2.inRange(image_hsv, lower_bound, upper_bound)

    return mask

# Function to find the centroid of the largest contour
def find_centroid_of_largest_contour(mask):
    """Trouve le centroïde du plus grand contour dans l'image binaire."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        moments = cv2.moments(largest_contour)

        if moments["m00"] != 0:
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
            return (cx, cy)

    return None

# Function to connect to WebSocket server
def websocket_connect():
    """Connect to WebSocket server."""
    global ws
    try:
        ws = websocket.create_connection(WEBSOCKET_URL)
        print("Connected to WebSocket server")
    except Exception as e:
        print(f"Error connecting to WebSocket: {e}")

# Function to send centroid to WebSocket server
def send_centroid_to_websocket(centroid):
    """Envoie le centroïde via WebSocket à un serveur."""
    if centroid is not None and ws is not None:
        data = {"centroid": {"x": centroid[0], "y": centroid[1]}}
        try:
            ws.send(json.dumps(data))  # Envoyer les données du centroïde en JSON
        except Exception as e:
            print(f"Erreur d'envoi via WebSocket: {e}")

# Function to generate frames from the camera
def gen_frames():
    """Generate video frames from the camera."""
    output = io.BytesIO()
    while True:
        picam2.capture_file(output, format='jpeg')
        frame = output.getvalue()
        BW = create_mask(frame)
        centroid = find_centroid_of_largest_contour(BW)
        send_centroid_to_websocket(centroid)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        output.seek(0)
        output.truncate()

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

if __name__ == '__main__':
    # Start WebSocket connection in a separate thread
    websocket_thread = threading.Thread(target=websocket_connect)
    websocket_thread.daemon = True
    websocket_thread.start()

    # Start Flask app
    app.run(host='0.0.0.0', port=1981)