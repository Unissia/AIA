# -*- coding: utf-8 -*-

import time
from rpi_ws281x import PixelStrip, Color

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

def color_wipe(color, wait_ms=10):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)
# Fonction pour éclairer toutes les LED en blanc au maximum de luminosité
def max_white_light(color, wait_ms=10):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)

try:
    # Appeler la fonction pour éclairer en blanc au max
    max_white_light(Color(255, 255, 150))

    # Maintenir l'éclairage jusqu'à ce que l'utilisateur interrompe le programme
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    color_wipe(Color(0, 0, 0))  # Éteindre les LED lors de l'interruption