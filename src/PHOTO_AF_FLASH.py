#!/usr/bin/python3

from sys import stdin
from termios import TCIOFLUSH, tcflush
from time import strftime
from libcamera import Transform
from gpiozero import Button
from picamera2 import Picamera2, Preview
from libcamera import controls
import time
from rpi_ws281x import PixelStrip, Color
import keyboard
import os

# Vérifier si le dossier PHOTOs existe, sinon le créer
photos_dir = "/home/unissia/Documents/PHOTO_AF_FLASH"
if not os.path.exists(photos_dir):
    os.makedirs(photos_dir)

# Configuration de la LED
LED_COUNT = 50        # Nombre de LED dans l'anneau
LED_PIN = 18          # Broche GPIO connectée aux LED (doit prendre en charge PWM)
LED_FREQ_HZ = 800000  # Fréquence des signaux PWM en hertz
LED_DMA = 10          # Canal DMA pour générer le signal PWM
LED_BRIGHTNESS = 255  # Luminosité des LED (0-255)
LED_INVERT = False    # Inverser le signal de contrôle (True pour les anodes communes)
LED_CHANNEL = 0       # Numéro du canal GPIO

# Initialisation de la LED
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Définition des broches GPIO pour les boutons
Btp = 17  # Le bouton connecté à la broche GPIO 17 (capture d'image).
btp_q = 27  # Le bouton connecté à la broche GPIO 27 (quitter le programme).
bouton = Button(Btp)  # Initialise le bouton de capture sur la broche 17.
quit = Button(btp_q)  # Initialise le bouton de sortie sur la broche 27.

cam = Picamera2()  # Initialise une instance de la caméra.

# Configuration de la caméra pour la capture d'image avec une résolution définie et une rotation verticale.
cam.start_preview(Preview.QTGL, x=600, y=200, width=1152, height=648, transform=Transform(vflip=1))
camera_config = cam.create_video_configuration(main={"size": (2304, 1296)})
cam.configure(camera_config)  # Applique la configuration à la caméra.

# Démarre l'aperçu de la caméra dans une fenêtre.
cam.start(show_preview=True)
DIST = 7

def flash_led():
    """Allume brièvement les LED pour simuler un flash."""
    # Allumer les LED en blanc
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(225, 200, 115))
    strip.show()
    time.sleep(0.25)  # Durée du flash (250 ms)
    # Éteindre les LED
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

def color_wipe(color, wait_ms=10):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)

try:
    while True:  # Boucle infinie pour surveiller les boutons.
        time.sleep(0.1)  # Réduit l'intervalle de vérification pour améliorer la réactivité.
        cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": DIST})

        if bouton.is_pressed or keyboard.is_pressed("p"):  # Si le bouton de capture est pressé...
            flash_led()  # Active le flash LED
            # Génère un nom de fichier basé sur la date et l'heure actuelles pour la capture d'image.
            filename = photos_dir + "/" + strftime("%Y%m%d-%H%M%S") + '.png'
            
            # Capture une image et la sauvegarde sous le nom de fichier généré.
            cam.capture_file(filename, format="png", wait=None)
            print(f"Captured {filename} successfully")  # Affiche un message de confirmation.
            
            # Petite pause pour éviter les captures multiples par erreur
            time.sleep(0.5)

        if quit.is_pressed:  # Si le bouton de sortie est pressé...
            print("Closing camera...")  # Affiche un message d'arrêt.
            break  # Quitte la boucle pour terminer le programme.

except KeyboardInterrupt:
    color_wipe(Color(0, 0, 0))  # Éteindre les LED lors de l'interruption

finally:
    # Cette section s'exécute à la fin du programme.
    cam.stop_preview()  # Arrête l'aperçu de la caméra.
    cam.stop()         # Arrête la caméra.
    cam.close()        # Ferme la caméra et libère les ressources.
    tcflush(stdin, TCIOFLUSH)  # Vide le tampon d'entrée du terminal.
