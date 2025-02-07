package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go_site/dataprocessing"
	ds "go_site/datastore"
	"go_site/websocketclient"
	"image"
	"image/color"
	"image/jpeg"
	"log"
	"math"
	"net/http"
	"os"
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
	camera      *gocv.VideoCapture
	DataChannel = make(chan ds.Centroid, 1000)
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
		// Simuler un timestamp de capture (remplace par une vraie source si nécessaire)
		captureTime := float64(time.Now().UnixNano())/1e9 - ds.TimeZero // Convertit en millisecondes
		print("Capture Time: ", captureTime)

		// Calcul de la distance en parallèle
		ComputeDistance(&centroid, captureTime)
	}
}

func ComputeDistance(centroid *ds.Centroid, captureTime float64) {
	ds.Mutex.Lock()
	defer ds.Mutex.Unlock()

	// Si le centroïde est vide, récupérer la dernière valeur stockée
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

	// Normalisation avec l'échelle
	diffX := float64(ds.Gauche.X - ds.Droite.X)
	diffY := float64(ds.Gauche.Y - ds.Droite.Y)
	scale := 0.1 / math.Sqrt(diffX*diffX+diffY*diffY)

	// Appliquer la normalisation et le signe
	distance = distance * scale * sign * 1000 // Conversion en millimètres

	// Ajouter la valeur au buffer circulaire
	ds.Values = append(ds.Values, []float64{distance, captureTime})

	// Limiter la taille du buffer
	if len(ds.Values) > ds.BufferSize {
		ds.Values = ds.Values[1:] // Supprime l'ancien élément
	}
}

func resetTimer() {

	// Initialisation de la bibliothèque periph.io
	if _, err := host.Init(); err != nil {
		fmt.Println("Erreur d'initialisation de periph.io:", err)
		return
	}
	// Réinitialisation du timer
	ds.TimeZero = float64(time.Now().UnixNano()) / 1e9
	// Accéder au GPIO 2 (BCM)
	pin := rpi.P1_3 // GPIO 2 correspond à la broche P1_3 sur Raspberry Pi
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

// Fonction pour diffuser le flux vidéo avec détection de centroïde
func streamVideo(c *gin.Context) {
	c.Header("Content-Type", "multipart/x-mixed-replace; boundary=frame")

	for {
		frame := gocv.NewMat()
		if ok := camera.Read(&frame); !ok {
			log.Println("Erreur lors de la lecture du frame")
			frame.Close()
			continue
		}

		// Détecter le centroïde
		centroid := dataprocessing.ProcessFrame(frame, ds.LowerBound, ds.UpperBound)

		// Dessiner un cercle sur l'image si le centroïde est trouvé
		if centroid.X != 0 && centroid.Y != 0 {
			gocv.Circle(&frame, image.Pt(int(centroid.X), int(centroid.Y)), 5, color.RGBA{R: 0, G: 0, B: 255, A: 255}, -1)
		} else {
			log.Println("Aucun centroïde détecté")
		}

		// Convertir l'image en JPEG
		var buf bytes.Buffer
		img, err := frame.ToImage()
		if err != nil {
			log.Println("Erreur lors de la conversion de l'image:", err)
			frame.Close()
			continue
		}
		jpeg.Encode(&buf, img, nil)

		// 🔹 Envoyer les données du centroïde dans le channel SANS BLOQUER
		select {
		case DataChannel <- centroid:
		default:
			log.Println("⚠️  Canal DataChannel plein, centroïde ignoré")
		}

		// 🔹 Libérer la mémoire de l'image immédiatement après traitement
		frame.Close()

		// Envoyer l'image via HTTP
		fmt.Fprintf(c.Writer, "--frame\r\nContent-Type: image/jpeg\r\n\r\n")
		c.Writer.Write(buf.Bytes())
		fmt.Fprintf(c.Writer, "\r\n")
		c.Writer.Flush()
	}
}

func main() {
	// Charger la configuration
	config, err := loadConfig("config.json")
	if err != nil {
		log.Fatal("Erreur de lecture du fichier config.json:", err)
	}

	ds.TimeZero = float64(time.Now().UnixNano()) / 1e9
	// Construire l'adresse du serveur
	serverAddress := fmt.Sprintf("%s:%d", config.ServerIP, config.ServerPort)

	// Ouvrir la caméra
	camera, err = gocv.OpenVideoCapture(0)
	if err != nil {
		log.Fatal("Erreur lors de l'ouverture de la caméra:", err)
	}
	defer camera.Close()

	// Configurer le serveur HTTP avec Gin
	r := gin.Default()

	// Route pour le flux vidéo
	r.GET("/stream", streamVideo)

	// 📌 2️⃣ Route `/` servant `test.html`
	r.GET("/", func(c *gin.Context) {
		c.File("templates/test.html")
	})

	// 📌 3️⃣ Route `/graph` servant `g.html`
	r.GET("/graph", func(c *gin.Context) {
		c.File("templates/g.html")
	})

	go ProcessCentroids()
	// Route pour obtenir les valeurs du centroïde

	r.GET("/camera_view", func(c *gin.Context) {
		html := `
		<html>
		<body>
		<img src="/stream">
		</body>
		</html>`
		c.Data(http.StatusOK, "text/html; charset=utf-8", []byte(html))
	})

	// 📌 4️⃣ API `/values` renvoyant `valuesSensor` en JSON
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

	// 📌 5️⃣ API `/values_camera` renvoyant `valuesCamera` en JSON
	r.GET("/values_camera", func(c *gin.Context) {
		ds.Mutex.Lock()
		defer ds.Mutex.Unlock()
		c.JSON(http.StatusOK, ds.Values)
	})
	r.GET("/speed_camera", func(c *gin.Context) {
		ds.ValuesVitesse = dataprocessing.ComputeSpeed(ds.Values)
		c.JSON(http.StatusOK, ds.ValuesVitesse)
	})

	// 📌 6️⃣ API `/values_motor` renvoyant `valuesMotor` en JSON
	r.GET("/values_motor", func(c *gin.Context) {
		ds.Mutex.Lock()
		defer ds.Mutex.Unlock()
		c.JSON(http.StatusOK, ds.ValuesMotor)
	})

	// Route pour réinitialiser le timer
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
	fmt.Println("Serveur démarré sur", serverAddress)
	if err := r.Run(serverAddress); err != nil {
		log.Fatal("Erreur lors du démarrage du serveur:", err)
	}
}
