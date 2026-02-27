import cv2
import numpy as np

img = cv2.imread("attacking.png")

hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# sprawdź piksel ze środka
h, w = hsv.shape[:2]
center_pixel = hsv[200, 150]

print("HSV:", center_pixel)