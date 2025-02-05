package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"image/jpeg"
	"log"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"gocv.io/x/gocv"
)

var (
	mutex  sync.Mutex
	camera *gocv.VideoCapture
	client websocketclient.WebSocketClient
	config map[string]interface{}
)

// loadConfig reads the configuration file and returns the settings as a map
func loadConfig(filename string) (map[string]interface{}, error) {
	var config map[string]interface{}
	file, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(file, &config)
	return config, err
}

// startCamera initializes the camera for capturing video
func startCamera() {
	var err error
	camera, err = gocv.OpenVideoCapture(0)
	if err != nil {
		log.Fatal("Error opening camera:", err)
	}
}

// sendDataLoop continuously processes frames and sends centroid data via WebSocket
func sendDataLoop() {
	for {
		frame := gocv.NewMat()
		if ok := camera.Read(&frame); !ok {
			log.Println("Failed to read frame from camera")
			continue
		}
		defer frame.Close()

		// Define HSV color range for object detection
		lowerBound := gocv.NewScalar(30, 150, 50, 0) // Example values
		upperBound := gocv.NewScalar(90, 255, 255, 0)

		// Process the frame to detect centroid
		centroid := dataprocessing.ProcessFrame(frame, lowerBound, upperBound)

		if centroid.X == 0 && centroid.Y == 0 {
			continue
		}

		// Prepare data in JSON format
		data := map[string]float32{
			"centroid_x": float32(centroid.X),
			"centroid_y": float32(centroid.Y),
		}
		jsonData, _ := json.Marshal(data)
		client.SendMessage(string(jsonData))

		time.Sleep(1 * time.Second) // Send data every second
	}
}

// streamVideo handles the video streaming endpoint using MJPEG format
func streamVideo(c *gin.Context) {
	c.Header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
	for {
		frame := gocv.NewMat()
		if ok := camera.Read(&frame); !ok {
			log.Println("Failed to read frame")
			continue
		}
		defer frame.Close()

		// Encode frame as JPEG and send it over HTTP
		var buf bytes.Buffer
		jpeg.Encode(&buf, frame.ToImage(), nil)
		fmt.Fprintf(c.Writer, "--frame\r\nContent-Type: image/jpeg\r\n\r\n")
		c.Writer.Write(buf.Bytes())
		fmt.Fprintf(c.Writer, "\r\n")
		c.Writer.Flush()
	}
}

func main() {
	var err error
	config, err = loadConfig("config.json")
	if err != nil {
		log.Fatal("Error loading config:", err)
	}

	// Retrieve WebSocket server details from config
	serverIP := config["matlab_socket_Server_IP_Adress"].(string)
	serverPort := int(config["matlab_socket_Server_Port"].(float64))
	wsURL := fmt.Sprintf("ws://%s:%d", serverIP, serverPort)

	// Initialize WebSocket client
	client = websocketclient.WebSocketClient{
		url:       wsURL,
		onMessage: func(msg string) { log.Println("Received:", msg) },
	}
	if err := client.Connect(); err != nil {
		log.Fatal("WebSocket connection error:", err)
	}

	// Start camera and launch data transmission
	startCamera()
	go sendDataLoop()

	// Setup API server
	r := gin.Default()
	r.GET("/stream", streamVideo) // Video streaming endpoint
	r.Run(":8080")                // Run server on port 8080
}
