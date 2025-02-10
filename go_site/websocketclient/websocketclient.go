package websocketclient

import (
	"encoding/json"
	ds "go_site/datastore"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

var (
	mutex     sync.Mutex
	clients   = make(map[*websocket.Conn]bool) // Liste des clients connectés
	broadcast = make(chan [][]float64)         // Canal pour diffuser les données
	upgrader  = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool {
			return true // Permet les connexions CORS pour WebSocket
		},
	}
)

// WebSocket handler qui gère chaque connexion dans une goroutine
func HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	// Mettre à niveau la connexion HTTP en WebSocket
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("WebSocket upgrade error:", err)
		return
	}

	// Lancer la gestion du WebSocket dans une goroutine
	go handleClient(conn)
}

// handleClient gère un client WebSocket de manière asynchrone
func handleClient(conn *websocket.Conn) {
	defer conn.Close()

	// Ajouter le client
	mutex.Lock()
	clients[conn] = true
	mutex.Unlock()
	log.Println("Nouvelle connexion WebSocket")

	// Définir un timeout pour éviter les connexions fantômes
	conn.SetReadDeadline(time.Now().Add(60 * time.Second))

	// Lancer une goroutine pour envoyer les données périodiquement
	//go sendPIDData(conn)

	// Lire les messages WebSocket en boucle
	for {
		_, messageJSON, err := conn.ReadMessage()
		if err != nil {
			log.Println("WebSocket read error:", err)
			break // Quitte la boucle si une erreur survient
		}

		// Réinitialiser le timeout après chaque message reçu
		conn.SetReadDeadline(time.Now().Add(60 * time.Second))

		// Traiter le message WebSocket
		processWebSocketMessage(messageJSON)
	}

	// Supprimer le client après la fermeture
	mutex.Lock()
	delete(clients, conn)
	mutex.Unlock()
	log.Println("Client WebSocket déconnecté")
}

// processWebSocketMessage traite et stocke un message WebSocket
func processWebSocketMessage(messageJSON []byte) {
	var message ds.WebSocketMessage

	// Décoder le message JSON
	if err := json.Unmarshal(messageJSON, &message); err != nil {
		log.Println("Erreur de décodage JSON:", err)
		return
	}

	// Vérifier la validité du message
	if len(message.Signal) < 3 || len(message.Signal[0].Input) == 0 {
		log.Println("Format JSON invalide")
		return
	}

	// Extraire les valeurs
	arduinoTime := message.Signal[0].Input[0]
	input := message.Signal[1].Input[0]
	motorInput := message.Signal[2].Input[0]

	// Stocker les données en mode thread-safe
	ds.Mutex.Lock()
	defer ds.Mutex.Unlock()

	// Ajouter les valeurs dans ValuesSensor
	ds.ValuesSensor = append(ds.ValuesSensor, []float64{input, arduinoTime})
	if len(ds.ValuesSensor) > ds.BufferSize {
		ds.ValuesSensor = ds.ValuesSensor[1:] // Supprime l'élément le plus ancien
	}

	// Ajouter les valeurs dans ValuesMotor
	ds.ValuesMotor = append(ds.ValuesMotor, []float64{motorInput - 90, arduinoTime})
	if len(ds.ValuesMotor) > ds.BufferSize {
		ds.ValuesMotor = ds.ValuesMotor[1:] // Supprime l'élément le plus ancien
	}
}

func sendPIDData(conn *websocket.Conn) {
	for {
		time.Sleep(1 * time.Second) // Envoi toutes les secondes

		// Lire les valeurs P, I, D en mémoire (sans historique)

		// Construire le message JSON
		jsonData := map[string]interface{}{
			"BlockID": "webpub 1",
			"Signal": []map[string]interface{}{
				{"DataType": "single", "Value": []float64{ds.Data.P}}, // P
				{"DataType": "single", "Value": []float64{ds.Data.I}}, // I
				{"DataType": "single", "Value": []float64{ds.Data.D}}, // D
			},
		}

		// Convertir en JSON
		message, err := json.Marshal(jsonData)
		if err != nil {
			log.Println("Erreur conversion JSON:", err)
			continue
		}

		// Envoyer aux clients WebSocket
		mutex.Lock()
		err = conn.WriteMessage(websocket.TextMessage, message)
		mutex.Unlock()

		if err != nil {
			log.Println("Erreur envoi WebSocket:", err)
			break // Arrêter l'envoi si le client se déconnecte
		}

	}
}
