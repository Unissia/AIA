#!/usr/bin/env python

"""
Ensemble de fonctions utilitaires pour l'analyse de l'image.
"""

import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import cv2
import os
import time
from sklearn.cluster import KMeans
from skimage.color import rgb2lab, lab2rgb, rgb2hsv, hsv2rgb
import math

__author__ = "Bastien Baudouin, Guillaume Polizzi"


def reframeImage(image, minX, maxX, minY, maxY):
    """
    Renvoie une portion de l'image.

    image: l'image à recadrer
    minX: Coordonnée X du coin supérieur gauche de l'image recadrée 
    maxX: Coordonnée X du coin inférieur droit de l'image recadrée
    minY: Coordonnée Y du coin supérieur gauche de l'image recadrée
    maxY: Coordonnée Y du coin inférieur droit de l'image recadrée

    return l'image recadrée
    """
    return image[minY:maxY, minX:maxX]


def measureFatThickness(image):
    """
    Mesure l'épaisseur minimale de la couche de gras sur une image.

    image: l'image à analyser

    return l'épaisseur de la couche de gras
    """
    # thresold d'acceptation
    differenceThresold = 70

    # Limites de la couche du gras
    topLimit = []
    bottomLimit = []

    # Recadrage manuel autour du nucleus medius
    image = reframeImage(image, 0, 300, 0, 400)

    # Recherche des pixels qui délimitent la couche de gras
    for x in range(0, image.shape[1]):
        color = image[0][x][2]
        layers = 0
        for y in range(0, image.shape[0]):
            if layers > 1:
                break

            if (abs(int(image[y][x][2]) - color) > differenceThresold): 
                if layers == 0:
                    topLimit.append((x, y))
                    color = int(image[y][x][2])
                    image[y][x] = [0, 0, 255]

                else:
                    bottomLimit.append((x, y))
                    color = int(image[y][x][2])
                    image[y][x] = [0, 255, 0]

                layers += 1
        
    # Calcul de l'épaisseur minimale de la couche de gras
    distance, cords = findSmallestThickness(topLimit, bottomLimit)
    print("Epaisseur minimale de la couche de gras: " + str(distance) + " pixels")
    print("Points retenus : " + str(cords)+"\n")
    image[cords[0][1]][cords[0][0]] = [255, 0, 0]
    image[cords[1][1]][cords[1][0]] = [255, 0, 0]

    return distance,cords


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


def drawPatternBox(image, pattern_nucleus, pattern_nucleus_2, pattern_list, image_kmean=None):
    """
    Dessine un rectangle autour des motifs de nucleus medius et de colonne vertébrale trouvés.

    image: l'image sur laquelle rechercher le motif
    """
    marker_nucleus = (0,0)
    marker_backbone = (0,0)

    nucleus_thresold = 0.6
    nucleus_thresold_2 = 0.6
    backbone_thresold = 0.4


    max_val_nucleus_2, top_left_nucleus, bottom_right_nucleus, top_left_nucleus_2, bottom_right_nucleus_2 = drawPatternBoxNucleus(image, pattern_nucleus, pattern_nucleus_2, nucleus_thresold, nucleus_thresold_2)
    best_backbone_pattern, top_left_backbone, bottom_right_backbone = drawPatternBoxBackbone(image, pattern_list, backbone_thresold)


    # On rajoute la prise de mesure grossière
    if max_val_nucleus_2 < nucleus_thresold_2: 
        x, y = bottom_right_nucleus
        marker_nucleus = (x - 40, y - 40)
    else:
        x, y = bottom_right_nucleus_2
        marker_nucleus = (x, y)
        
    x_2,y_2 = top_left_backbone
    x_3, y_3 = bottom_right_backbone
    marker_backbone = (marker_nucleus[0], int((y_2 + y_3) / 2))

    epaisseur_muscle = marker_backbone[1] -  marker_nucleus[1]
    # On vérifie si les cotes sont bien situé en dessous du nucleus, 
    # si ce n'est pas le cas c'est que la détecton à été mal effectuée 
    if (marker_nucleus[1] < marker_backbone[1]):
        cv2.line(image, marker_nucleus, marker_backbone, (255, 0, 0), 2)
    else: 
        best_backbone_pattern = None

    if (image_kmean is not None):
            cv2.rectangle(image_kmean, top_left_backbone, bottom_right_backbone, (0, 255, 0), 2)
            cv2.rectangle(image_kmean, top_left_nucleus_2, bottom_right_nucleus_2, (0, 0, 255), 2)
            cv2.line(image_kmean, marker_nucleus, marker_backbone, (255, 0, 0), 2)
    print(f"Epaisseur de la couche de muscle : {epaisseur_muscle} pixels")
    print(f"Coordonnées du points bas du nucleus: {marker_nucleus}\n")
    return [image,image_kmean, best_backbone_pattern is not None, top_left_nucleus, bottom_right_nucleus, marker_nucleus, marker_backbone]


def drawPatternBoxNucleus(image, pattern_nucleus, pattern_nucleus_2, nucleus_thresold, nucleus_thresold_2):
    """
    Dessine un rectangle autour du nucleus medius.

    image: l'image sur laquelle rechercher le motif
    pattern: le motif à rechercher
    """
    result_nucleus = cv2.matchTemplate(image, pattern_nucleus, cv2.TM_CCOEFF_NORMED)
    _, max_val_nucleus, _, max_loc_nucleus = cv2.minMaxLoc(result_nucleus)

    if max_val_nucleus > nucleus_thresold:
        h, w, _ = pattern_nucleus.shape
        top_left_nucleus = max_loc_nucleus
        bottom_right_nucleus = (top_left_nucleus[0] + w, top_left_nucleus[1] + h)
        cv2.rectangle(image, top_left_nucleus, bottom_right_nucleus, (0, 255, 0), 2)
        
        # Extraction de la région d'intérêt (ROI) correspondant à la zone détectée par "pattern_nucleus"
        roi_nucleus = image[top_left_nucleus[1]:bottom_right_nucleus[1], top_left_nucleus[0]:bottom_right_nucleus[0]]
        
        # Recherche de "pattern_nucleus_2" dans la région d'intérêt
        result_nucleus_2 = cv2.matchTemplate(roi_nucleus, pattern_nucleus_2, cv2.TM_CCOEFF_NORMED)
        _, max_val_nucleus_2, _, max_loc_nucleus_2 = cv2.minMaxLoc(result_nucleus_2)
        
        if max_val_nucleus_2 > nucleus_thresold_2:
            h_2, w_2, _ = pattern_nucleus_2.shape
            top_left_nucleus_2 = (max_loc_nucleus_2[0] + top_left_nucleus[0], max_loc_nucleus_2[1] + top_left_nucleus[1])
            bottom_right_nucleus_2 = (top_left_nucleus_2[0] + w_2, top_left_nucleus_2[1] + h_2)
            cv2.rectangle(image, top_left_nucleus_2, bottom_right_nucleus_2, (0, 0, 255), 2)

    return max_val_nucleus_2, top_left_nucleus, bottom_right_nucleus, top_left_nucleus_2, bottom_right_nucleus_2


def drawPatternBoxBackbone(image, pattern_list, backbone_thresold):
    """
    Dessine un rectangle autour de la colonne vertébrale.

    image: l'image sur laquelle rechercher le motif
    pattern_list: les motifs à rechercher
    """
    best_match_score = float('-inf')
    best_max_loc = None
    best_backbone_pattern = None

    for pattern_backbone in pattern_list:
        result_backbone = cv2.matchTemplate(image, pattern_backbone, cv2.TM_CCOEFF_NORMED)
        _, max_val_backbone, _, max_loc_backbone = cv2.minMaxLoc(result_backbone)

        if max_val_backbone > backbone_thresold and max_val_backbone > best_match_score:
            best_match_score = max_val_backbone
            best_max_loc = max_loc_backbone
            best_backbone_pattern = pattern_backbone

    if best_backbone_pattern is not None:
        h, w, _ = best_backbone_pattern.shape
        top_left_backbone = best_max_loc
        bottom_right_backbone = (top_left_backbone[0] + w, top_left_backbone[1] + h)
        cv2.rectangle(image, top_left_backbone, bottom_right_backbone, (0, 255, 0), 2)

    return best_backbone_pattern, top_left_backbone, bottom_right_backbone


def applyKmeans(initial_image, k):
    """
    Réduit le nombre de couleurs d'une image à l'aide de l'algorithme K-Means.

    initial_image: l'image à traiter
    k: le nombre de couleurs à conserver

    return l'image traitée
    """
    image = initial_image
    pixel_matrix = np.array(image)
    
    # Redimensionner la matrice de pixels en une liste de pixels
    pixels = pixel_matrix.reshape(-1, 3)

    # Appliquer K-Means pour réduire les couleurs
    kmeans = KMeans(n_clusters=k, random_state=10, n_init=10)
    kmeans.fit(pixels)
    labels = kmeans.predict(pixels)
    cluster_centers = kmeans.cluster_centers_

    # Remplacer les couleurs des pixels par les couleurs moyennes des catégories
    pixels_reduced = cluster_centers[labels].reshape(pixel_matrix.shape)

    # Créer une nouvelle image à partir des pixels réduits
    image_reduced = Image.fromarray(pixels_reduced.astype('uint8')) 
    return image_reduced
