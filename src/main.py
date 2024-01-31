#!/usr/bin/env python
"""
Programme principal d'analyse d'images de carcasses de porc.
"""

import cv2 as cv
from utils import *

__author__ = "Bastien Baudouin, Guillaume Polizzi"


# Chargement de l'image
img = cv.imread("./img/test/test-simplified-1.png")

measureFatThickness(img)