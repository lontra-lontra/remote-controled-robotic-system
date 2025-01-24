from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import random
import time
from threading import Thread

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Function to simulate real-time data
def generate_data():
    while True:
        time.sleep(2)  # Wait for 2 seconds
        random_value = random.randint(0, 100)  # Simulate a random data point
        current_time = time.strftime('%H:%M:%S')  # Current time as label
        socketio.emit('update_data', {'time': current_time, 'value': random_value})  # Send data to client

# Start the data generator in a separate thread
@app.before_first_request
def start_data_thread():
    thread = Thread(target=generate_data)
    thread.daemon = True
    thread.start()

# API endpoint to serve data (useful for debugging or HTTP clients)
@app.route('/api/data', methods=['GET'])
def get_data():
    random_value = random.randint(0, 100)
    current_time = time.strftime('%H:%M:%S')
    return jsonify({'time': current_time, 'value': random_value})

# Serve the HTML page
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True)
