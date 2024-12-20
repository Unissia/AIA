#!/bin/bash

# Modifier /boot/config.txt
echo "Modification de /boot/config.txt..."
sudo sed -i 's/camera_auto_detect=1/camera_auto_detect=0/' /boot/config.txt
if ! grep -q "^dtoverlay=imx708" /boot/config.txt; then
  echo "dtoverlay=imx708" | sudo tee -a /boot/config.txt
fi
echo "Modifications de /boot/config.txt terminées."

# Mettre à jour le système
echo "Mise à jour du système..."
sudo apt update && sudo apt upgrade -y

# Installer les bibliothèques nécessaires
echo "Installation des bibliothèques nécessaires..."

pip3 install rpi_ws281x gpiozero keyboard

echo "Installation des dépendances terminée."

# Reboot pour appliquer les modifications
echo "Configuration terminée. Redémarrage du système..."
sudo reboot
