#!/usr/bin/env python
"""
Programme principal d'analyse d'images de carcasses de porc.
"""

import cv2 as cv
from utils import *

__author__ = "Bastien Baudouin, Guillaume Polizzi"


# Chargement de l'image
img = cv.imread("./img/carc1.jpg")

img2 = reframeImage(img, 0, 200, 0, 400)
cv.imshow("Display window", img2)
k = cv.waitKey(0) # Wait for a keystroke in the window