#!/usr/bin/env python

"""
Ensemble de fonctions utilitaires pour l'analyse de l'image.
"""

import cv2 as cv
import math

__author__ = "Bastien Baudouin, Guillaume Polizzi"


def reframeImage(img, minX, maxX, minY, maxY):
    """
    Renvoie une portion de l'image.

    img: l'image à recadrer
    minX: Coordonnée X du coin supérieur gauche de l'image recadrée 
    maxX: Coordonnée X du coin inférieur droit de l'image recadrée
    minY: Coordonnée Y du coin supérieur gauche de l'image recadrée
    maxY: Coordonnée Y du coin inférieur droit de l'image recadrée

    return l'image recadrée
    """
    return img[minY:maxY, minX:maxX]


def measureFatThickness(img):
    """
    Mesure l'épaisseur minimale de la couche de gras sur une image.

    img: l'image à analyser

    return l'épaisseur de la couche de gras
    """
    # Seuil d'acceptation
    differenceThresold = 50

    # Limites de la couche du gras
    topLimit = []
    bottomLimit = []

    # Recadrage manuel autour du nucleus medius
    img = reframeImage(img, 0, 300, 0, 400)

    # Recherche des pixels qui délimitent la couche de gras
    for x in range(0, img.shape[1]):
        color = img[0][x][2]
        layers = 0
        for y in range(0, img.shape[0]):
            if layers > 1:
                break
            
            if (abs(int(img[y][x][2]) - color) > differenceThresold): #img[y][x][2] != color:
                if layers == 0:
                    topLimit.append((x, y))
                    img[y][x] = [0, 0, 255]
                else:
                    bottomLimit.append((x, y))
                    img[y][x] = [0, 255, 0]

                layers += 1
                color = img[y][x][2]
        
    # Calcul de l'épaisseur minimale de la couche de gras
    distance, cords = findSmallestThickness(topLimit, bottomLimit)
    print("Epaisseur minimale de la couche de gras: " + str(distance) + " pixels")
    print("Points retenus : " + str(cords))
    img[cords[0][1]][cords[0][0]] = [255, 0, 0]
    img[cords[1][1]][cords[1][0]] = [255, 0, 0]

    cv.namedWindow("Display window", cv.WINDOW_NORMAL)
    cv.resizeWindow("Display window", 800, 900)
    cv.imshow("Display window", img)
    k = cv.waitKey(0) # Wait for a keystroke in the window
    return 0

def findSmallestThickness(topLimit, bottomLimit):
    """
    Trouve l'épaisseur minimale de la couche de gras.
    Calcule la distance minimale entre les pixels de la limite supérieure et inférieure de la couche de gras.

    topLimit: pixels de la limite supérieure de la couche de gras
    bottomLimit: pixels de la limite inférieure de la couche de gras

    return la distance minimale entre les deux ensembles de pixels
    """
    distance = 10000
    cords = []
    for pixelTop in topLimit:
        for pixelBottom in bottomLimit:
            d = math.sqrt((pixelTop[0] - pixelBottom[0])**2 + (pixelTop[1] - pixelBottom[1])**2)
            if d < distance:
                distance = d
                cords = [pixelTop, pixelBottom]

    return distance, cords
