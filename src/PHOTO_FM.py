#!/usr/bin/python3

from sys import stdin
from termios import TCIOFLUSH, tcflush
from time import strftime
from libcamera import Transform
from gpiozero import Button

from picamera2 import Picamera2, Preview
# GPIO pins for buttons 
Btp = 17
btp_q = 27
bouton = Button(Btp)
quit = Button(btp_q)

key_flag = False
cam = Picamera2()

# Configuration pour la prévisualisation et la capture
camera_config = cam.create_still_configuration(main={"size": (4056, 3040)}, transform=Transform(vflip=1))
cam.configure(camera_config)

# Démarrage de la prévisualisation
#cam.start_preview(Preview.QTGL)
cam.start(show_preview=True)

try:
    while True:
        if bouton.is_pressed:
            if not key_flag:
                key_flag = True

                # Capture de l'image en haute résolution
                filename = "/home/unissia/Documents/PHOTOS_KERMENE_FM/" + strftime("%Y%m%d-%H%M%S") + '.png'
                cam.capture_file(filename, format="png",wait=None)
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