#!/usr/bin/env python

"""
Ensemble de fonctions utilitaires pour l'analyse de l'image.
"""

import cv2 as cv

__author__ = "Bastien Baudouin, Guillaume Polizzi"


# Code de démo
img = cv.imread("./img/carc1.jpg")

cv.imshow("Display window", img)
k = cv.waitKey(0) # Wait for a keystroke in the window