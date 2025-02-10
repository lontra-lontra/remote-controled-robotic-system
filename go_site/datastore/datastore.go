package datastore

import (
	"sync"

	"gocv.io/x/gocv"
)

type Config struct {
	ServerIP   string `json:"server_ip"`
	ServerPort int    `json:"server_port"`
}

type WebSocketMessage struct {
	Signal []struct {
		Input []float64 `json:"Value"`
	} `json:"Signal"`
}

type Centroid struct {
	X float32 `json:"centroid_x"`
	Y float32 `json:"centroid_y"`
}

type Input struct {
	P float64 `json:"P"`
	I float64 `json:"I"`
	D float64 `json:"D"`
}

// Buffer pour stocker les valeurs des capteurs
var (
	Mutex               sync.Mutex
	LowerBound          = gocv.NewScalar(0.00*180, 0.329*255, 0.381*255, 0)  // H, S, V
	UpperBound          = gocv.NewScalar(0.004*180, 0.892*255, 0.930*255, 0) // H, S, V
	TimeZero            float64
	ValuesSensor        [][]float64
	ValuesMotor         [][]float64
	Values              = [][]float64{}
	ValuesVitesse       = [][]float64{}
	ValuesSensorVitesse = [][]float64{}
	BufferSize          = 1000 // Taille du buffer, ajustable
	DataChannel         = make(chan Centroid, 10)
	Centre              = Centroid{X: 402, Y: 271}
	Gauche              = Centroid{X: 577, Y: 319}
	Droite              = Centroid{X: 232, Y: 252}
	Data                = Input{}
)
