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
    # Seuils
    fatRedThresold = 120
    meatRedDifferenceThresold = 50

    # Recadrage manuel autour du nucleus medius
    img = reframeImage(img, 0, 300, 0, 400)

    # Recherche des pixels qui délimitent la couche de gras
    for x in range(0, img.shape[1]):
        background = True
        fatRed = -1
        for y in range(10, img.shape[0]):
            # Traitement sur l'arrière plan sombre
            if (background):
                if (img[y][x][2] > fatRedThresold):
                    background = False
                    img[y][x][1] = 255
            # Traitements sur la couche de gras
            else:
                if (fatRed == -1):
                    # On récupère le niveau de rouge qui sera utilisé en référence
                    fatRed = img[y+5][x][2]

                if (abs(int(img[y][x][2]) - int(fatRed)) > meatRedDifferenceThresold):
                    img[y][x][1] = 255
                    break

                    # ToDo: Ajuster la méthode de comparaison des niveaux de rouge pour éviter les ratés sur des zones moins différentes
                    # Il faudrait peut-être comparer la différence de rouge avec plusieurs pixels précédents

    # Calcul de l'épaisseur minimale de la couche de gras

    cv.namedWindow("Display window", cv.WINDOW_NORMAL)
    cv.resizeWindow("Display window", 800, 1000)
    cv.imshow("Display window", img)
    k = cv.waitKey(0) # Wait for a keystroke in the window
    return 0