import threading
import os
import cv2
import math
import time
import numpy as np
from keras.preprocessing.image import load_img, img_to_array
import matplotlib.pyplot as plt
from keras.models import load_model

timer = time.time()


def FindSmallestThickness(topLimit,lower_boundary):
    # Initialisation des variables pour stocker la distance minimale et les coordonnées
    distance = 10000
    cords = []

    # Calcul de la plus petite distance entre les points de topLimit et lower_boundary
    for pixelTop in topLimit:
        for pixelBottom in lower_boundary:
            d = math.sqrt((pixelTop[0] - pixelBottom[0])**2 + (pixelTop[1] - pixelBottom[1])**2)
            if d < distance:
                distance = d
                cords = [pixelTop, pixelBottom]
    return(distance,cords)


def MeasureFatThickness(image,image_path):
    
    temps_debut = time.time()
          
    ###################### MeasureMuscleLimit #########################################################################################################
        
    # Paramètres de l'image (doivent correspondre à ceux utilisés pour l'entraînement)
    img_height, img_width = 256, 256
    
    # Charger et prétraiter l'image de test
    test_img = load_img(image_path, target_size=(img_height, img_width))
    test_img_array = img_to_array(test_img) / 255.0  # Normalisation
    test_img_array = np.expand_dims(test_img_array, axis=0)  # Ajouter une dimension pour le batch

    # Prédire le masque pour l'image de test
    predicted_mask = model.predict(test_img_array)

    # Convertir la prédiction en masque binaire (0 ou 1)
    predicted_mask = (predicted_mask > 0.5).astype(np.uint8)
    predicted_mask = np.squeeze(predicted_mask)  # Supprimer la dimension du batch

    # Trouver les indices des pixels où l'objet est présent (valeurs de 1 dans le masque)
    object_pixels = np.where(predicted_mask == 1)

    if len(object_pixels[0]) > 0:  # Si des pixels de l'objet sont détectés
        # Récupérer les coordonnées xmin, xmax
        xmin = np.min(object_pixels[1])  # Le minimum des coordonnées x
        xmax = np.max(object_pixels[1])  # Le maximum des coordonnées x
        
        # Trouver les y correspondants au xmax
        y_for_xmax = object_pixels[0][np.argmax(object_pixels[1])]  # y correspondant à xmax
        
        coord_gluteus = (xmax,y_for_xmax)
        
        # Liste pour stocker les coordonnées de la limite inférieure
        lower_boundary = []

        # Trouver les y min correspondant à chaque x entre xmin et xmax (limite inférieure)
        for x in range(xmin, xmax + 1):
            y_values = object_pixels[0][object_pixels[1] == x]  # Obtenir tous les y pour un x donné
            if len(y_values) > 0:  # S'assurer qu'il y a des pixels pour ce x
                y_min = np.min(y_values)  # Le y min pour ce x
                lower_boundary.append((x, y_min))  # Ajouter les coordonnées (x, y_min) à la liste
                image[y_min][x] = [0, 255, 0]
    else:
        # Si aucun objet n'est détecté, initialiser les valeurs par défaut
        xmin, xmax, coord_gluteus, lower_boundary = None, None, None, []

    
    #################################################################################################################################################
    
    
    ###################### MeasureFatLimit ##########################################################################################################
    
    # Initialisation de `distance` et `cords` par défaut pour éviter les erreurs dans les prints
    distance, cords = None, None
    
    # Vérifier si xmin, xmax, et lower_boundary sont définis
    if xmin is not None and xmax is not None and lower_boundary:
        # Seuil d'acceptation
        differenceThresold = 70

        # Limites de la couche du gras
        topLimit = []
        # Recherche des pixels qui délimitent la couche de gras
        for x in range(xmin, xmax+1):
            color = image[0][x][2]  # Composante rouge (canal 2 en BGR)
            layers = 0
            for y in range(0, image.shape[0]):
                if layers > 1:
                    break

                if abs(int(image[y][x][2]) - color) > differenceThresold:
                    if layers == 0:
                        topLimit.append((x, y))
                        color = int(image[y][x][2])  # Mettre à jour la couleur pour la prochaine comparaison
                        image[y][x] = [0, 255, 0]    # Colorer en rouge
                    layers += 1
        
    #################################################################################################################################################
        if topLimit and lower_boundary:
            distance, cords = FindSmallestThickness(topLimit, lower_boundary)
            dist_mm = distance * 0.731
            if cords:
                # Récupérer les coordonnées des points haut et bas
                pixelTop, pixelBottom = cords

                # Tracer une ligne rouge entre les deux points
                cv2.line(image, (pixelTop[0], pixelTop[1]), (pixelBottom[0], pixelBottom[1]), (0, 0, 255), 1)
                
                
                scale_percent = 100  # Ajuster ce pourcentage si l'image est trop grande ou trop petite
                width = int(image.shape[1] * scale_percent / 100)
                height = int(image.shape[0] * scale_percent / 100)
                image = cv2.resize(image, (width, height))

                # Afficher l'image avec la ligne tracée
                """cv2.imshow("Image avec distance minimale", image)
                cv2.waitKey(0)  # Attendre qu'une touche soit pressée pour fermer la fenêtre
                cv2.destroyAllWindows()
                #cv2.imwrite('./RESU/resultat_epaisseur_minimale.png', image)"""
        else:
            print("Aucune limite supérieure ou inférieure n'a été détectée.")
    else:
        print("Aucun objet détecté dans l'image.")
        
        
    # Affichage des données seulement si elles sont définies
    if distance is not None and cords is not None:
        dist_mm = distance * 0.731
        print("Distance minimale :", distance, "px")
        print("Distance minimale :", dist_mm, "mm")
        print("Coordonnées des points :", cords)
    else:
        print("Aucune distance minimale ou coordonnées valides n'ont été détectées.")


   
    duree = time.time() - temps_debut
    print(f"Le programme a mis {duree} secondes à s'exécuter")

    return image, coord_gluteus if coord_gluteus else (0, 0)


def ajout_box(image,coord_glut):
    # Initialiser les variables avec des valeurs par défaut
    repere_cotes = (0, 0)
    best_template_cotes = None
    
    
    # On recherche les côtes
    best_match_score = float('-inf')
    best_max_loc = None

    for template_cotes in liste_motifs:
        result_cotes = cv2.matchTemplate(image, template_cotes, cv2.TM_CCOEFF_NORMED)
        _, max_val_cotes, _, max_loc_cotes = cv2.minMaxLoc(result_cotes)
        seuil_cotes = 0.4
        
        if max_val_cotes > seuil_cotes and max_val_cotes > best_match_score:
            best_match_score = max_val_cotes
            best_max_loc = max_loc_cotes
            best_template_cotes = template_cotes
    
    if best_template_cotes is not None:
        h, w, _ = best_template_cotes.shape
        top_left_cotes = best_max_loc
        bottom_right_cotes = (top_left_cotes[0] + w, top_left_cotes[1] + h)
        cv2.rectangle(image, top_left_cotes, bottom_right_cotes, (0, 255, 0), 1)
        
        x_2, y_2 = top_left_cotes
        x_3, y_3 = bottom_right_cotes
        repere_cotes = (coord_glut[0], int((y_2 + y_3) / 2))
        
        # On vérifie si les côtes sont bien situées en dessous du nucleus, si ce n’est pas le cas c’est que la détection a été mal effectuée 
        if coord_glut[1] < repere_cotes[1]:
            cv2.line(image, coord_glut, repere_cotes, (255, 0, 0), 1)
        else:
            best_template_cotes = None
        
        
        scale_percent = 300  # Ajuster ce pourcentage si l'image est trop grande ou trop petite
        width = int(image.shape[1] * scale_percent / 100)
        height = int(image.shape[0] * scale_percent / 100)
        image = cv2.resize(image, (width, height))
    
    return (image)


motif_directory = './img/MOTIFS/COL_CNN_256/'

# Initialisation de la liste des motifs
liste_motifs = []

# Parcours de tous les fichiers dans le répertoire de motifs
for filename in os.listdir(motif_directory):
    # Vérification de l'extension du fichier
    if filename.endswith(('.png', '.jpg', '.jpeg')):
        # Construction du chemin complet du motif
        motif_path = os.path.join(motif_directory, filename)
        # Lecture du motif
        motif = cv2.imread(motif_path)
        # Vérification si la lecture a réussi
        if motif is not None:
            # Ajout du motif à la liste
            liste_motifs.append(motif)
        else:
            print(f"Error: Could not read the image {motif_path}")


# Charger le modèle U-Net sauvegardé
model = load_model('C:/Users/Paul/Documents/ALGO_PIGSEL/PIGSEL_AIA/MODELES_IA_H5/MODEL_VAC.h5')
         
dossier_source = './RESEAU_FINAL/TEST_IM4'
chemin_destination = "./RESEAU_FINAL/RESULTAT_IM4"


nb_images = 0 
images_valides = 0
temps_debut = time.time()

# Vérifier si le dossier cible existe, sinon le créer
if not os.path.exists(chemin_destination):
    os.makedirs(chemin_destination)


for nom_fichier in os.listdir(dossier_source):
    chemin_image = os.path.join(dossier_source, nom_fichier)
    nb_images += 1
    # Vérifier si le fichier est une image (extension png, jpg, etc.)
    if os.path.isfile(chemin_image) and nom_fichier.lower().endswith(('.png', '.jpg', '.jpeg')):
        # Appeler la fonction de traitement pour chaque image
        img = cv2.imread(chemin_image)
        imageFat,coord = MeasureFatThickness(img,chemin_image)
        img_finale = ajout_box(imageFat,coord)
        
        output_path = os.path.join(chemin_destination, f'{os.path.splitext(nom_fichier)[0]}_result.png')
        cv2.imwrite(output_path,img_finale)
        
duree = time.time() - temps_debut
print(f"Le programme a mis {duree} secondes à s'exécuter pour {nb_images} images. dont {images_valides} images valides")


"""cv2.imshow("img finale",img_finale)
cv2.waitKey(0)  # Attendre qu'une touche soit pressée pour fermer la fenêtre
cv2.destroyAllWindows"""

duree = time.time()-timer
print("la durre est de :",duree) 