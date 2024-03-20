#!/usr/bin/env python
"""
Programme principal d'analyse d'images de carcasses de porc.
"""

from utils import *
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import cv2
import os
import time
from sklearn.cluster import KMeans
from skimage.color import rgb2lab, lab2rgb, rgb2hsv, hsv2rgb

__author__ = "Bastien Baudouin, Guillaume Polizzi"

start_time = time.time()

# Chargement de l'image
image = cv2.imread("./img/000002.jpg")

# Chargement des motifs du nucleus medius et de la colonne vertébrale
pattern_nucleus = cv2.imread('./img/Motifs/Nucleus/motif_nucleus_1.png')
if pattern_nucleus is None:
    print("Erreur: Impossible de charger le motif du nucleus medius.")
    exit()

pattern_nucleus_2 = cv2.imread('./img/Motifs/Nucleus/motif_nucleus_2.png')
if pattern_nucleus_2 is None:
    print("Erreur: Impossible de charger le motif de la pointe du nucleus medius.")
    exit()

# Initialisation de la liste des motifs
pattern_directory = './img/Motifs/colonne/'
pattern_list = []

# Parcours de tous les fichiers dans le répertoire de motifs
for filename in os.listdir(pattern_directory):
    # Vérification de l'extension du fichier
    if filename.endswith('.png'):
        # Construction du chemin complet du motif
        pattern_path = os.path.join(pattern_directory, filename)
        # Lecture du motif
        pattern = cv2.imread(pattern_path)
        if pattern is not None:
            pattern_list.append(pattern)
        else:
            print(f"Erreur: Impossible de charger l'image {pattern_path}.")

# Dossiers de stockage des images intermédiaires et résultats
source_folder = "./Images_originales"
destination_folder = "./Resultats"

# Mesure de gras
simplified_image = applyKmeans(image, 2)
simplified_image = cv2.cvtColor(np.array(simplified_image), cv2.COLOR_BGR2RGB)
Image.fromarray(simplified_image).save('./img/Resultats/kmean.jpg')
fat_measure, coord_fat = measureFatThickness(cv2.imread('./img/Resultats/kmean.jpg'))


# Mesure de viande
[image, simplified_image, _, _, _, _, _]=drawPatternBox(image, pattern_nucleus, pattern_nucleus_2, pattern_list,simplified_image)

# Ajout de la ligne de mesure de gras
cv2.line(image, coord_fat[0], coord_fat[1], [255, 0, 0], 2)
cv2.line(simplified_image, coord_fat[0], coord_fat[1], [255, 0, 0], 2)

# Sauvegarde des images
Image.fromarray(image).save('./img/Resultats/Result.jpg')
Image.fromarray(simplified_image).save('./img/Resultats/Result_simplified.jpg')

print("Temps d'exécution: %s secondes" % (time.time() - start_time))

# %%
