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
import cv2
import numpy as np

# Répertoire pour stocker les photos capturées
photos_dir = "/home/unissia/Documents/PHOTO_AF_FLASH"
if not os.path.exists(photos_dir):
    os.makedirs(photos_dir)

# Fichiers images statiques à afficher pour les états 1, 2 et 3
photo_state1 = "/home/unissia/Documents/DEPOTOIR/0069.png"
photo_state2 = "/home/unissia/Documents/DEPOTOIR/0069.jpg"
photo_state3 = "/home/unissia/Documents/DEPOTOIR/0069.jpg"

# Configuration de la LED
LED_COUNT      = 50
LED_PIN        = 12
LED_FREQ_HZ    = 800000
LED_DMA        = 10
LED_BRIGHTNESS = 255
LED_INVERT     = False
LED_CHANNEL    = 0

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Boutons pour la machine à états
quit_btn = Button(27)   # Bouton de fermeture
bp1 = Button(21)        # Pour passer de l'état 0 à l'état 1
bp2 = Button(16)        # Dans état 1, passe à l'état 2
bp3 = Button(20)        # Dans état 1, passe à l'état 3

cam = Picamera2()

# Dimensions pour le redimensionnement de la preview
screen_width = 800
screen_height = 480
camera_width = 2304
camera_height = 1296

target_ratio = screen_width / screen_height
camera_ratio = camera_width / camera_height

if camera_ratio > target_ratio:
    scaled_height = screen_height
    scaled_width = int(camera_width * (scaled_height / camera_height))
else:
    scaled_width = screen_width
    scaled_height = int(camera_height * (scaled_width / camera_width))

x_offset = (screen_width - scaled_width) // 2
y_offset = (screen_height - scaled_height) // 2

preview_config = cam.create_preview_configuration(
    main={"size": (camera_width, camera_height)},
    transform=Transform(vflip=1),
    buffer_count=2
)
cam.configure(preview_config)
cam.start_preview(Preview.QTGL, x=x_offset, y=y_offset, width=scaled_width, height=scaled_height)
cam.start()

DIST = 7

def flash_led():
    """Allume brièvement les LED pour simuler un flash."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(225, 200, 115))
    strip.show()
    time.sleep(0.25)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

def color_wipe(color, wait_ms=10):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)

# Fonction pour charger et redimensionner une image overlay (avec canal alpha)
def load_overlay_image(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print("Erreur de chargement de", path)
        return None
    # Si l'image a 3 canaux, la convertir en 4 canaux (B,G,R,A)
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    img = cv2.resize(img, (scaled_width, scaled_height))
    return img

overlay1 = load_overlay_image(photo_state1)
overlay2 = load_overlay_image(photo_state2)
overlay3 = load_overlay_image(photo_state3)

# Fonction pour effacer l'overlay en appliquant une image transparente
def clear_overlay():
    transparent = np.zeros((scaled_height, scaled_width, 4), dtype=np.uint8)
    cam.set_overlay(transparent)

# Effacer l'overlay initialement
clear_overlay()

# Variable d'état de la machine
state = 0

try:
    while True:
        time.sleep(0.1)
        
        # État 0 : Prévisualisation en temps réel sans overlay
        if state == 0:
            cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": DIST})
            clear_overlay()
            if bp1.is_pressed:
                state = 1
                time.sleep(0.2)  # anti-rebond
        
        # État 1 : Flash, capture et affichage d'un overlay statique (overlay1)
        elif state == 1:
            flash_led()
#             filename = photos_dir + "/" + strftime("%Y%m%d-%H%M%S") + '.png'
#             cam.capture_file(filename, format="png", wait=None)
#             print(f"Captured {filename} successfully")
            if overlay1 is not None:
                cam.set_overlay(overlay1)
            # Attendre la transition via BP2 ou BP3
            while True:
                if bp2.is_pressed:
                    state = 2
                    break
                elif bp3.is_pressed:
                    state = 3
                    break
                elif quit_btn.is_pressed:
                    state = -1
                    break
                time.sleep(0.1)
            if state == -1:
                break
            clear_overlay()
        
        # État 2 : Afficher overlay2 pendant 1.5 s puis retour à l'état 0
        if state == 2:
            if overlay2 is not None:
                cam.set_overlay(overlay2)
            time.sleep(1.5)
            clear_overlay()
            state = 0
        
        # État 3 : Afficher overlay3 pendant 1.5 s puis retour à l'état 0
        if state == 3:
            if overlay3 is not None:
                cam.set_overlay(overlay3)
            time.sleep(1.5)
            clear_overlay()
            state = 0
        
        # Possibilité de quitter depuis n'importe quel état
        if quit_btn.is_pressed or keyboard.is_pressed("q"):
            print("Closing camera...")
            break

except KeyboardInterrupt:
    color_wipe(Color(0, 0, 0))

finally:
    cam.stop_preview()
    cam.stop()
    cam.close()
    tcflush(stdin, TCIOFLUSH)
