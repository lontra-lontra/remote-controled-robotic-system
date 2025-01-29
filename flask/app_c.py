import io
import logging
import threading
import json
from flask import Flask, Response, request, jsonify
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
import websocket
import cv2 import imread
import numpy as np


# Charger l'image avec OpenCV
img = cv2.imread("mon_image.jpg")

# Convertir l'image en bytes
image_bytes = img.tobytes()


app = Flask(__name__)

# Camera setup
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

# WebSocket settings
WEBSOCKET_URL = "ws://172.16.16.134:8080"
ws = None

def create_mask(image_path):
    """Charge une image JPEG, applique un masque basé sur des seuils HSV et retourne uniquement le masque binaire."""
    
    # Charger l'image en couleur (BGR par défaut)
    image = cv2.imread(image_path)
    
    # Vérifier si l'image est bien chargée
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

def send_centroid_to_websocket(centroid, ws_url=WEBSOCKET_URL):
    """Envoie le centroïde via WebSocket à un serveur."""
    if centroid is not None:
        # Préparer les données sous forme JSON
        data = {
            "centroid": {
                "x": centroid[0],
                "y": centroid[1]
            }
        }
        
        # Ouvrir la connexion WebSocket et envoyer les données
        try:
            ws = websocket.create_connection(ws_url)
            ws.send(json.dumps(data))  # Envoyer les données du centroïde en JSON
            ws.close()
        except Exception as e:
            print(f"Erreur de connexion WebSocket: {e}")




def websocket_connect():
    """Connect to WebSocket server."""
    global ws
    try:
        ws = websocket.create_connection(WEBSOCKET_URL)
        print("Connected to WebSocket server")
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
        
        BW = create_mask(frame)
        centroid = find_centroid_of_largest_contour(BW)
        send_centroid_to_websocket(centroid)
        print("voila le centroid!!!!!!!!!!", centroid)

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

    
@app.route('/api/record-video', methods=['POST'])
def record_video():
    """Record a 2-second video."""
    output = io.BytesIO()
    encoder = JpegEncoder()
    file_output = FileOutput(output)

    try:
        picam2.start_recording(encoder, file_output)
        threading.Event().wait(10)  # Record for 10 seconds
        picam2.stop_recording()

        output.seek(0)
        video_data = output.read()

        return Response(video_data, mimetype='video/jpeg')
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
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