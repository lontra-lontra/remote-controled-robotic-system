import io
from picamera2 import Picamera2
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
folder_path = os.path.join(current_dir, '/frames')
# Camera setup
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

def gen_frames():
    """Generate video frames from the camera and save them to a file."""
    output = io.BytesIO()
    frame_number = 0
    while True:
        picam2.capture_file(output, format='jpeg.json')
        frame = output.getvalue()
        
        # Save the frame to a file
        with open(os.path.join(folder_path, f'frame_{frame_number}.jpg'), 'wb') as f:
            f.write(frame)
        frame_number += 1
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        output.seek(0)
        output.truncate()
