package main

import (
	"fmt"

	"github.com/gorilla/websocket"
)

// WebSocketClient gère la connexion WebSocket
type WebSocketClient struct {
	url       string
	conn      *websocket.Conn
	onMessage func(string)
}

// Connect établit la connexion WebSocket
func (client *WebSocketClient) Connect() error {
	var err error
	client.conn, _, err = websocket.DefaultDialer.Dial(client.url, nil)
	if err != nil {
		return err
	}

	// Démarrer la lecture des messages en arrière-plan
	go func() {
		for {
			_, message, err := client.conn.ReadMessage()
			if err != nil {
				fmt.Println("WebSocket Read Error:", err)
				return
			}
			client.onMessage(string(message))
		}
	}()
	return nil
}

// SendMessage envoie un message WebSocket
func (client *WebSocketClient) SendMessage(msg string) error {
	return client.conn.WriteMessage(websocket.TextMessage, []byte(msg))
}
