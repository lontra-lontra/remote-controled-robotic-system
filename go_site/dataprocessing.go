package dataprocessing

import (
	"image"
	"sync"

	"gocv.io/x/gocv"
)

var (
	mutex sync.Mutex
)

// CreateMask applies a color filter to isolate a specific object in the frame
func CreateMask(frame gocv.Mat, lowerBound, upperBound gocv.Scalar) gocv.Mat {
	mutex.Lock()
	defer mutex.Unlock()

	// Convert image from BGR to HSV
	hsv := gocv.NewMat()
	gocv.CvtColor(frame, &hsv, gocv.ColorBGRToHSV)

	// Apply color filtering
	mask := gocv.NewMat()
	gocv.InRangeWithScalar(hsv, lowerBound, upperBound, &mask)
	hsv.Close()

	return mask
}

// FindCentroidOfLargestContour finds the centroid of the largest detected contour
func FindCentroidOfLargestContour(mask gocv.Mat) image.Point {
	mutex.Lock()
	defer mutex.Unlock()

	contours := gocv.FindContours(mask, gocv.RetrievalExternal, gocv.ChainApproxSimple)
	largestArea := 0.0
	centroid := image.Point{}

	for i := 0; i < contours.Size(); i++ {
		area := gocv.ContourArea(contours.At(i))
		if area > largestArea {
			largestArea = area
			moment := gocv.Moments(contours.At(i), false)
			if moment.M00 != 0 {
				centroid = image.Pt(int(moment.M10/moment.M00), int(moment.M01/moment.M00))
			}
		}
	}
	return centroid
}

// ProcessFrame processes an image to detect the centroid of the largest object in a given color range
func ProcessFrame(frame gocv.Mat, lowerBound, upperBound gocv.Scalar) image.Point {
	mutex.Lock()
	defer mutex.Unlock()

	mask := CreateMask(frame, lowerBound, upperBound)
	centroid := FindCentroidOfLargestContour(mask)
	mask.Close()

	return centroid
}
