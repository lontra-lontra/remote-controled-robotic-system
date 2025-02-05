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
import RPi.GPIO as GPIO


time_zero = time.time()

buffer_size = 1000
centre = (402, 271)
plus_loing = (577, 319)
plus_proche = (232, 252)




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
values_sensor =[]
values_motor =[]

if config["camera"]:
    picam2 = Picamera2()
    # Initialize the camera
    
    
    # Configure camera

    picam2.configure(
        picam2.create_preview_configuration(
        main={"size": (640, 480)},
        buffer_count=2
    )
    )
    
    # Start the camera
    picam2.start()
    
    # Allow camera to warm up
    time.sleep(2)
    


frame = None
should_stop = False

def correction(pos, centre_roue):
    """ Prend la position mesuree, la position de la roue et rend l'ecart a l'equilibre (non renormee). On suppose que le centre de rotation est 100 pixels plus bas"""
    centre_roue = np.array(centre_roue)
    pb = np.array(pos - centre_roue)
    centre_rot = np.array([centre_roue[0], centre_roue[1]-100])
    vec = np.array(centre_roue-centre_rot)
    theta = np.arctan(pb[1]/pb[0])
    rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    centre_roue = centre_rot +rot.dot(vec)
    pb = np.array(pos - centre_roue)
    return pb


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
    

    while not should_stop:
        capture_time = time.time() - time_zero
        
        # Capture frame (en RGB)
        frame = picam2.capture_array()
        
        if (1 == 1):
            # Traiter l'image
            processed_frame, mask, centroid = process_frame(frame)
            

            
            # Convert frame to jpg for streaming
            ret, buffer = cv2.imencode('.jpg', processed_frame)
            frame_bytes = buffer.tobytes()
            
            if centroid is None:
                centroid = values[-1]

            sign = np.sign(centroid[0] - centre[0]) 
            #pb = correction(centroid, centre)
            pb = np.array(centroid) - np.array(centre)
            distance = np.linalg.norm(pb)


            scale = 0.1/np.linalg.norm(np.array(plus_loing) - np.array(plus_proche))
            
            distance = distance * scale * sign 
            distance = distance*1000
            values.append([distance, capture_time])


            if len(values) > buffer_size:
                values.pop(0)
        else:
            frame_bytes = frame



        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


    
    # Cleanup
    picam2.stop()








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
    return jsonify(values_sensor)

@app.route('/values_camera', methods=['GET'])
def l_camera():
    return jsonify(values)

@app.route('/values_motor', methods=['GET'])
def l_motor():
    return jsonify(values_motor)



def reset_timer():
    # Set up GPIO
    global time_zero 
    
    time_zero = time.time() # reset the time to zero
                            # reset arduino time to zero
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(2, GPIO.OUT)
    # Set GPIO2 high
    GPIO.output(2, GPIO.HIGH)
    time.sleep(0.1)
    # Set GPIO2 low
    GPIO.output(2, GPIO.LOW)

    # Clean up GPIO
    GPIO.cleanup()



# Route for sending data over WebSocket
@app.route('/api/send-data', methods=['POST'])
def send_data():
    reset_timer()

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
