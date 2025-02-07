package main

import (
	"image"

	"gocv.io/x/gocv"
)

// ProcessFrame détecte le centroïde d'un objet dans une plage HSV
func ProcessFrame(frame gocv.Mat, lowerBound, upperBound gocv.Scalar) image.Point {
	// Convertir en HSV
	hsv := gocv.NewMat()
	defer hsv.Close()
	gocv.CvtColor(frame, &hsv, gocv.ColorBGRToHSV)

	// Appliquer le masque
	mask := gocv.NewMat()
	defer mask.Close()
	gocv.InRangeWithScalar(hsv, lowerBound, upperBound, &mask)

	// Détecter le plus grand contour et extraire le centroïde
	contours := gocv.FindContours(mask, gocv.RetrievalExternal, gocv.ChainApproxSimple)
	var largestArea float64 = 0
	centroid := image.Point{}

	for i := 0; i < contours.Size(); i++ {
		area := gocv.ContourArea(contours.At(i))
		if area > largestArea {
			largestArea = area
			moments := gocv.Moments(contours.At(i), false)
			if moments.M00 != 0 {
				centroid = image.Pt(int(moments.M10/moments.M00), int(moments.M01/moments.M00))
			}
		}
	}
	return centroid
}
