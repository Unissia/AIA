#!/usr/bin/python3

from sys import stdin
from termios import TCIOFLUSH, tcflush
from time import strftime
from libcamera import Transform
from gpiozero import Button
from picamera2 import Picamera2, Preview
from libcamera import controls

# GPIO pins for buttons
Btp = 17
btp_q = 27
bouton = Button(Btp)
quit = Button(btp_q)

key_flag = False
cam = Picamera2()

# Configuration pour la prévisualisation et la capture avec autofocus continu
camera_config = cam.create_still_configuration(main={"size": (2304, 1296)}, transform=Transform(vflip=1))
cam.configure(camera_config)

# Activer l'autofocus continu
#cam.set_controls({"AfMode":controls.AfModeEnum.Continuous})

# Démarrage de la prévisualisation
cam.start_preview(Preview.QTGL, x=600, y=200, width=1152, height=648)
cam.start()

#with cam.controls as controls:
    #controls.AnalogueGain = 0.0
    #controls.create_still_configuration(main={"size": (4608, 2592)}, transform=Transform(vflip=1))
    #controls.set_controls({"AfMode":controls.AfModeEnum.Auto})

try:
    while True:
        if bouton.is_pressed:
            if not key_flag:
                key_flag = True

                # Capture de l'image en haute résolution
                filename = "/home/unissia/Documents/PHOTOS_KERMENE_AF/" + strftime("%Y%m%d-%H%M%S") + '.png'
                cam.capture_file(filename, format="png", wait=None)
                print(f"Captured {filename} successfully")
        
        else:
            key_flag = False  # Remise à False pour éviter les captures répétées

        if quit.is_pressed:
            print("Closing camera...")
            break

finally:
    cam.stop_preview()
    cam.stop()
    cam.close()
    tcflush(stdin, TCIOFLUSH)
