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
sudo pip install rpi_ws281x gpiozero keyboard
echo "Installation des dépendances terminée."

# Créer et configurer le fichier de service camera_app.service
echo "Création du fichier de service camera_app.service..."
cat <<EOL | sudo tee /etc/systemd/system/camera_app.service
[Unit]
Description=Camera Application
After=multi-user.target graphical.target

[Service]
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/python3 /home/unissia/Documents/AIA/src/PHOTO_AF.py
ExecStop=/usr/bin/python3 -c "from rpi_ws281x import PixelStrip, Color; strip=PixelStrip(50, 18, 800000, 10, False, 255, 0); strip.begin(); [strip.setPixelColor(i, Color(0, 0, 0)) for i in range(strip.numPixels())]; strip.show()"
WorkingDirectory=/home/unissia/Documents/AIA/src
Restart=always
User=root
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/unissia/.Xauthority

[Install]
WantedBy=multi-user.target
EOL

# Recharger les unités systemd et activer le service
echo "Rechargement de systemd et activation du service..."
sudo systemctl daemon-reload
sudo systemctl enable camera_app.service
sudo systemctl start camera_app.service

# Reboot pour appliquer les modifications
echo "Configuration terminée. Redémarrage du système..."
sudo reboot
