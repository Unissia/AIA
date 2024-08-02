import cv2
import numpy as np
import time
from sklearn.cluster import KMeans

import os
import cv2

start_time = time.time()

folder_path = "./img/SOURCE/IMG_FM_3007/"
output_folder = "./img/SOURCE/IMG_FM_3007_REDIM"
nb_images = 0 
temps_debut = time.time()

# Vérifier si le dossier cible existe, sinon le créer
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def resize_image(image, new_width=None, new_height=None):
    # Déterminer la nouvelle taille de l'image en conservant le ratio d'aspect
    if new_width is None and new_height is None:
        return image  # Aucun redimensionnement n'est nécessaire
    elif new_width is None:
        ratio = new_height / image.shape[0]
        new_width = int(image.shape[1] * ratio)
    elif new_height is None:
        ratio = new_width / image.shape[1]
        new_height = int(image.shape[0] * ratio)
    
    # Redimensionner l'image en utilisant l'interpolation
    resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    return resized_image

def resize_images_in_folder(folder_path, output_folder, new_width=None, new_height=None):
    numero_photo = 1
    # Créer le dossier de sortie s'il n'existe pas
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Parcourir toutes les images dans le dossier d'entrée
    for filename in os.listdir(folder_path):
        # Vérifier si le fichier est une image
        if filename.endswith(('.jpg', '.jpeg', '.png', '.bmp')):
            # Charger l'image
            image_path = os.path.join(folder_path, filename)
            image = cv2.imread(image_path)
            
            # Redimensionner l'image
            resized_image = resize_image(image, new_width, new_height)
            
            nouveau_nom = str(numero_photo).zfill(4) + os.path.splitext(filename)[1]
            # Renommer le fichier
            os.rename(os.path.join(folder_path, filename), os.path.join(folder_path, nouveau_nom))
            # Incrémenter le compteur de photo
            numero_photo += 1
            
            # Enregistrer l'image redimensionnée dans le dossier de sortie
            output_path = os.path.join(output_folder, filename)
            cv2.imwrite(output_path, resized_image)




    

# Redimensionner toutes les images dans le dossier spécifié
resize_images_in_folder(folder_path, output_folder, new_width=500)  # Changer la largeur désirée ici

print("Temps d'exécution: %s secondes" % (time.time() - start_time))

