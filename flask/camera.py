import io
from picamera2 import Picamera2

# Camera setup
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

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
