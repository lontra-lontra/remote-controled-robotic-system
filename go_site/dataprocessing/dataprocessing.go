package dataprocessing

import (
	"image/color"
	"math"
	"sync"

	"gonum.org/v1/gonum/diff/fd"

	ds "go_site/datastore"

	"gocv.io/x/gocv"
)

var mutex sync.Mutex

// ProcessFrame détecte le centroïde d'un objet dans une plage HSV
func ProcessFrame(frame gocv.Mat, lowerBound, upperBound gocv.Scalar) ds.Centroid {
	// Convertir en HSV
	hsv := gocv.NewMat()
	defer hsv.Close()
	gocv.CvtColor(frame, &hsv, gocv.ColorBGRToHSV)

	// Appliquer le masque
	mask := gocv.NewMat()
	defer mask.Close()
	gocv.InRangeWithScalar(hsv, lowerBound, upperBound, &mask)

	// Trouver les contours
	contours := gocv.FindContours(mask, gocv.RetrievalExternal, gocv.ChainApproxSimple)
	var largestArea float64 = 0
	centroid := ds.Centroid{}

	for i := 0; i < contours.Size(); i++ {
		contour := contours.At(i) // Contour au format PointVector
		area := gocv.ContourArea(contour)
		if area > largestArea {
			largestArea = area

			// Créer un masque pour ce contour
			contourMask := gocv.NewMatWithSize(mask.Rows(), mask.Cols(), gocv.MatTypeCV8U)
			defer contourMask.Close()

			// Dessiner le contour sur le masque
			gocv.DrawContours(&contourMask, contours, i, color.RGBA{R: 255, G: 255, B: 255, A: 0}, -1)

			// Calculer les moments avec le masque binaire
			moments := gocv.Moments(contourMask, true)
			if m00, exists := moments["m00"]; exists && m00 != 0 {
				centroid = ds.Centroid{
					X: float32(moments["m10"] / m00),
					Y: float32(moments["m01"] / m00),
				}

			}
		}
	}

	return centroid
}

// 📌 1️⃣ Calculer la vitesse à partir de `Values`
func ComputeSpeed(table [][]float64) [][]float64 {
	mutex.Lock()
	defer mutex.Unlock()

	if len(table) < 3 { // Besoin d'au moins 3 points pour la dérivée
		return [][]float64{}
	}

	// Extraire distances et temps
	distances := make([]float64, len(table))
	times := make([]float64, len(table))
	for i, v := range table {
		distances[i], times[i] = v[0], v[1]
	}

	// Fonction interpolée
	f := func(x float64) float64 {
		for i := 1; i < len(times); i++ {
			if x < times[i] {
				return distances[i-1] + (x-times[i-1])*(distances[i]-distances[i-1])/(times[i]-times[i-1])
			}
		}
		return distances[len(distances)-1] // Retourne la dernière valeur
	}

	// Calcul de la vitesse (dérivée centrale)
	speedData := [][]float64{}
	for i := 1; i < len(times)-1; i++ {
		vitesse := fd.Derivative(f, times[i], &fd.Settings{Formula: fd.Central, Step: (times[i+1] - times[i-1]) / 2})
		if !math.IsNaN(vitesse) && !math.IsInf(vitesse, 0) {
			speedData = append(speedData, []float64{vitesse, times[i]})
		}
	}

	return speedData
}
