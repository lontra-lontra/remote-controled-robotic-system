package websocketclient

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"sync"

	"github.com/gorilla/websocket"
)

// Config structure to load JSON configuration
type Config struct {
	ServerIP   string `json:"matlab_socket_Server_IP_Adress"`
	ServerPort int    `json:"matlab_socket_Server_Port"`
}

// WebSocketClient handles WebSocket connections
type WebSocketClient struct {
	conn      *websocket.Conn
	url       string
	mutex     sync.Mutex
	connected bool
	onMessage func(string)
}

// Load configuration from file
func LoadConfig(filename string) (Config, error) {
	var config Config
	file, err := os.ReadFile(filename)
	if err != nil {
		return config, err
	}
	err = json.Unmarshal(file, &config)
	return config, err
}

// Connect to WebSocket server
func (client *WebSocketClient) Connect() error {
	var err error
	client.conn, _, err = websocket.DefaultDialer.Dial(client.url, nil)
	if err != nil {
		return err
	}
	client.connected = true

	go client.listen()
	return nil
}

// Listen for incoming messages
func (client *WebSocketClient) listen() {
	for {
		_, message, err := client.conn.ReadMessage()
		if err != nil {
			log.Println("Read error:", err)
			client.connected = false
			return
		}
		client.onMessage(string(message))
	}
}

// Send message to WebSocket server
func (client *WebSocketClient) SendMessage(msg string) error {
	client.mutex.Lock()
	defer client.mutex.Unlock()

	if !client.connected {
		return fmt.Errorf("WebSocket is not connected")
	}

	return client.conn.WriteMessage(websocket.TextMessage, []byte(msg))
}

// Close WebSocket connection
func (client *WebSocketClient) Close() {
	client.conn.Close()
	client.connected = false
}
