#!/usr/bin/env python

"""
Ensemble de fonctions utilitaires pour l'analyse de l'image.
"""

import cv2 as cv

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
    # Recadrage manuel autour du nucleus medius
    img = reframeImage(img, 0, 300, 0, 400)

    # Recherche des pixels qui délimitent la couche de gras
    for x in range(0, img.shape[1]):
        background = True
        for y in range(0, img.shape[0]):
            if (not background) or (img[y][x][2] > 100):
                background = False

    # Calcul de l'épaisseur minimale de la couche de gras

    cv.imshow("Display window", img)
    k = cv.waitKey(0) # Wait for a keystroke in the window
    return 0