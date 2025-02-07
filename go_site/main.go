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
	client WebSocketClient
	config map[string]interface{}
)

// loadConfig charge la configuration depuis un fichier JSON
func loadConfig(filename string) (map[string]interface{}, error) {
	var config map[string]interface{}
	file, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(file, &config)
	return config, err
}

// startCamera initialise la caméra
func startCamera() {
	var err error
	camera, err = gocv.OpenVideoCapture(0)
	if err != nil {
		log.Fatal("Error opening camera:", err)
	}
}

// sendDataLoop traite les images et envoie les centroïdes via WebSocket
func sendDataLoop() {
	for {
		frame := gocv.NewMat()
		if ok := camera.Read(&frame); !ok {
			log.Println("Failed to read frame from camera")
			continue
		}
		defer frame.Close()

		// Définir les seuils HSV
		lowerBound := gocv.NewScalar(30, 150, 50, 0) // Exemple
		upperBound := gocv.NewScalar(90, 255, 255, 0)

		// Détecter le centroïde
		centroid := ProcessFrame(frame, lowerBound, upperBound)

		if centroid.X == 0 && centroid.Y == 0 {
			continue
		}

		// Envoyer les données en JSON via WebSocket
		data := map[string]float32{
			"centroid_x": float32(centroid.X),
			"centroid_y": float32(centroid.Y),
		}
		jsonData, _ := json.Marshal(data)
		client.SendMessage(string(jsonData))

		time.Sleep(1 * time.Second) // Envoi toutes les secondes
	}
}

// streamVideo envoie le flux vidéo via HTTP (MJPEG)
// streamVideo envoie le flux vidéo en MJPEG
func streamVideo(c *gin.Context) {
	c.Header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
	for {
		frame := gocv.NewMat()
		if ok := camera.Read(&frame); !ok {
			log.Println("Failed to read frame")
			continue
		}
		defer frame.Close()

		// 🔹 Correction ici : Gestion de l'erreur avec ToImage()
		img, err := frame.ToImage()
		if err != nil {
			log.Println("Error converting frame to image:", err)
			continue
		}

		// Encoder en JPEG
		var buf bytes.Buffer
		jpeg.Encode(&buf, img, nil)
		fmt.Fprintf(c.Writer, "--frame\r\nContent-Type: image/jpeg\r\n\r\n")
		c.Writer.Write(buf.Bytes())
		fmt.Fprintf(c.Writer, "\r\n")
		c.Writer.Flush()
	}
}

// main initialise la configuration et démarre le serveur
func main() {
	var err error
	config, err = loadConfig("config.json")
	if err != nil {
		log.Fatal("Error loading config:", err)
	}

	// Charger l'URL WebSocket
	serverIP := config["matlab_socket_Server_IP_Adress"].(string)
	serverPort := int(config["matlab_socket_Server_Port"].(float64))
	wsURL := fmt.Sprintf("ws://%s:%d", serverIP, serverPort)

	// Initialiser WebSocket
	client = WebSocketClient{
		url:       wsURL,
		onMessage: func(msg string) { log.Println("Received:", msg) },
	}
	if err := client.Connect(); err != nil {
		log.Fatal("WebSocket connection error:", err)
	}

	// Démarrer la caméra et le traitement
	startCamera()
	go sendDataLoop()

	// Lancer le serveur HTTP pour la vidéo
	r := gin.Default()
	r.GET("/stream", streamVideo)
	r.Run(":8080") // Port 8080
}
