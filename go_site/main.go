package main

import (
	"encoding/json"
	"fmt"
	"go_site/dataprocessing"
	ds "go_site/datastore"
	"go_site/websocketclient"
	"image"
	"image/color"
	"log"
	"math"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"gocv.io/x/gocv"
	"periph.io/x/conn/v3/gpio"
	"periph.io/x/host/v3"
	"periph.io/x/host/v3/rpi"
)

type Config struct {
	ServerIP   string `json:"server_ip"`
	ServerPort int    `json:"server_port"`
}

var (
	cameraMutex  sync.RWMutex
	stream       *gocv.VideoCapture
	lastImg      []byte
	prevImg      []byte
	imgReady     bool // Indicateur pour savoir si une image est prï¿½te
	targetStream = "http://192.168.1.58:8080/stream"
	DataChannel  = make(chan ds.Centroid, 100) // Canal pour stocker les centroï¿½des

)

// Fonction pour charger la configuration depuis `config.json`
func loadConfig(filename string) (Config, error) {
	var config Config
	file, err := os.ReadFile(filename)
	if err != nil {
		return config, err
	}

	err = json.Unmarshal(file, &config)
	return config, err
}

func ProcessCentroids() {
	for centroid := range DataChannel {
		// Simuler un timestamp de capture (remplace par une vraie source si nÃ©cessaire)
		captureTime := float64(time.Now().UnixNano())/1e9 - ds.TimeZero // Convertit en millisecondes
		print("Capture Time: ", captureTime)

		// Calcul de la distance en parallÃ¨le
		ComputeDistance(&centroid, captureTime)
	}
}

func ComputeDistance(centroid *ds.Centroid, captureTime float64) {
	ds.Mutex.Lock()
	defer ds.Mutex.Unlock()

	// Si le centroÃ¯de est vide, rÃ©cupÃ©rer la derniÃ¨re valeur stockÃ©e
	if (*centroid == ds.Centroid{}) && len(ds.Values) > 0 {
		lastValue := ds.Values[len(ds.Values)-1]
		centroid.X = float32(lastValue[0])
		centroid.Y = float32(lastValue[1])
	}

	// Calcul du signe de direction
	sign := math.Copysign(1, float64(centroid.X-ds.Centre.X))

	// Vecteur de correction
	pbX := float64(centroid.X - ds.Centre.X)
	pbY := float64(centroid.Y - ds.Centre.Y)

	// Norme du vecteur (distance euclidienne)
	distance := math.Sqrt(pbX*pbX + pbY*pbY)

	// Normalisation avec l'Ã©chelle
	diffX := float64(ds.Gauche.X - ds.Droite.X)
	diffY := float64(ds.Gauche.Y - ds.Droite.Y)
	scale := 0.1 / math.Sqrt(diffX*diffX+diffY*diffY)

	// Appliquer la normalisation et le signe
	distance = distance * scale * sign * 1000 // Conversion en millimÃ¨tres

	// Ajouter la valeur au buffer circulaire
	ds.Values = append(ds.Values, []float64{distance, captureTime})

	// Limiter la taille du buffer
	if len(ds.Values) > ds.BufferSize {
		ds.Values = ds.Values[1:] // Supprime l'ancien Ã©lÃ©ment
	}
}

func resetTimer() {

	// Initialisation de la bibliothÃ¨que periph.io
	if _, err := host.Init(); err != nil {
		fmt.Println("Erreur d'initialisation de periph.io:", err)
		return
	}
	// RÃ©initialisation du timer
	ds.TimeZero = float64(time.Now().UnixNano()) / 1e9
	// AccÃ©der au GPIO 2 (BCM)
	pin := rpi.P1_3 // GPIO 2 correspond Ã  la broche P1_3 sur Raspberry Pi
	// Mettre GPIO 2 en sortie
	if err := pin.Out(gpio.High); err != nil {
		fmt.Println("Erreur en mettant GPIO HIGH:", err)
		return
	}
	// Attendre 100ms
	time.Sleep(100 * time.Millisecond)
	// Mettre GPIO 2 en LOW
	if err := pin.Out(gpio.Low); err != nil {
		fmt.Println("Erreur en mettant GPIO LOW:", err)
		return
	}
}

func resetValues() {
	ds.Values = [][]float64{}
	ds.ValuesVitesse = [][]float64{}
	ds.ValuesSensor = [][]float64{}
	ds.ValuesSensorVitesse = [][]float64{}
	ds.ValuesMotor = [][]float64{}
}

func captureFrames() {
	for {
		frame := gocv.NewMat()

		// ? Lire un frame sans ralentir le flux
		if !stream.Read(&frame) || frame.Empty() {
			frame.Close()
			continue
		}

		// ? Traitement du centroï¿½de en parallï¿½le pour ne pas bloquer le stream
		go func(frameCopy gocv.Mat) {
			centroid := dataprocessing.ProcessFrame(frameCopy, ds.LowerBound, ds.UpperBound)

			// ? Envoyer le centroï¿½de dans `DataChannel` sans bloquer
			select {
			case DataChannel <- centroid:
			default:
				// ? Canal plein, on ignore ce centroï¿½de pour ï¿½viter de bloquer
			}

			// ? Dessiner un cercle si un centroï¿½de est dï¿½tectï¿½
			if centroid.X != 0 && centroid.Y != 0 {
				gocv.Circle(&frameCopy, image.Pt(int(centroid.X), int(centroid.Y)), 5, color.RGBA{R: 255, G: 0, B: 0, A: 255}, -1)
			}
			frameCopy.Close()
		}(frame.Clone())

		// ? Encodage JPEG ultra-rapide
		imgBuf, err := gocv.IMEncode(gocv.JPEGFileExt, frame)
		if err == nil {
			cameraMutex.Lock()
			prevImg = lastImg // Sauvegarde de l'ancienne image pour ï¿½viter les coupures
			lastImg = imgBuf.GetBytes()
			imgReady = true
			cameraMutex.Unlock()
		}
		imgBuf.Close()
		frame.Close()
	}
}

func streamVideo(c *gin.Context) {
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("Content-Type", "multipart/x-mixed-replace; boundary=frame")

	for {
		// ? Rï¿½cupï¿½rer la derniï¿½re image immï¿½diatement
		cameraMutex.RLock()
		img := lastImg
		if !imgReady {
			img = prevImg // Si la nouvelle image n'est pas prï¿½te, utiliser l'ancienne
		}
		cameraMutex.RUnlock()

		// ? Envoi rapide de l?image en HTTP
		if len(img) > 0 {
			_, _ = fmt.Fprintf(c.Writer, "--frame\r\nContent-Type: image/jpeg\r\n\r\n")
			_, _ = c.Writer.Write(img)
			_, _ = fmt.Fprintf(c.Writer, "\r\n")
			c.Writer.Flush()
		}
	}
}

func main() {
	// Charger la configuration
	config, err := loadConfig("config.json")
	if err != nil {
		log.Fatal("Erreur de lecture du fichier config.json:", err)
	}

	sourceStream := "udp://127.0.0.1:5000"
	stream, err = gocv.VideoCaptureFile(sourceStream)
	if err != nil {
		log.Fatal("? Impossible d'ouvrir le flux UDP :", sourceStream)
	}
	defer stream.Close()

	ds.TimeZero = float64(time.Now().UnixNano()) / 1e9
	// Construire l'adresse du serveur
	serverAddress := fmt.Sprintf("%s:%d", config.ServerIP, config.ServerPort)

	go captureFrames()
	// Configurer le serveur HTTP avec Gin
	r := gin.Default()

	// Route pour le flux vidÃ©o
	r.GET("/stream", streamVideo)

	// ð 2ï¸â£ Route `/` servant `test.html`
	r.GET("/", func(c *gin.Context) {
		c.File("templates/test.html")
	})

	// ð 3ï¸â£ Route `/graph` servant `g.html`
	r.GET("/graph", func(c *gin.Context) {
		c.File("templates/g.html")
	})

	go ProcessCentroids()
	// Route pour obtenir les valeurs du centroÃ¯de

	r.GET("/camera_view", func(c *gin.Context) {
		html := `
		<html>
		<body>
		<img src="/stream">
		</body>
		</html>`
		c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(html))
	})

	// ð 4ï¸â£ API `/values` renvoyant `valuesSensor` en JSON
	r.GET("/values_sensor", func(c *gin.Context) {
		ds.Mutex.Lock()
		defer ds.Mutex.Unlock()
		c.JSON(http.StatusOK, ds.ValuesSensor)
	})

	//API '/values_sensor_vitesse' renvoyant 'valuesSensorVitesse' en JSON
	r.GET("/values_sensor_vitesse", func(c *gin.Context) {
		ds.ValuesSensorVitesse = dataprocessing.ComputeSpeed(ds.ValuesSensor)
		c.JSON(http.StatusOK, ds.ValuesSensorVitesse)
	})

	// ð 5ï¸â£ API `/values_camera` renvoyant `valuesCamera` en JSON
	r.GET("/values_camera", func(c *gin.Context) {
		ds.Mutex.Lock()
		defer ds.Mutex.Unlock()
		c.JSON(http.StatusOK, ds.Values)
	})
	r.GET("/speed_camera", func(c *gin.Context) {
		ds.ValuesVitesse = dataprocessing.ComputeSpeed(ds.Values)
		c.JSON(http.StatusOK, ds.ValuesVitesse)
	})

	// ð 6ï¸â£ API `/values_motor` renvoyant `valuesMotor` en JSON
	r.GET("/values_motor", func(c *gin.Context) {
		ds.Mutex.Lock()
		defer ds.Mutex.Unlock()
		c.JSON(http.StatusOK, ds.ValuesMotor)
	})

	// Route pour rÃ©initialiser le timer
	r.GET("/reset", func(c *gin.Context) {
		resetTimer()
		resetValues()
	})

	// Route pour le serveur WebSocket
	r.GET("/ws", func(c *gin.Context) {
		websocketclient.HandleWebSocket(c.Writer, c.Request) // tenter avec une go routine
		resetTimer()
		resetValues()
	})

	// Lancer le serveur avec l'adresse IP et le port de `config.json`
	fmt.Println("Serveur dÃ©marrÃ© sur", serverAddress)
	if err := r.Run(serverAddress); err != nil {
		log.Fatal("Erreur lors du dÃ©marrage du serveur:", err)
	}
}
