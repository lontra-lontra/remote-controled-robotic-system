
import numpy as np
import cv2
import time

time_zero = time.time()

from picamera2 import Picamera2

buffer_size = 100
centre = (402, 271)
plus_loing = (577, 319)
plus_proche = (232, 252)

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



def generate_frames(values):
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







