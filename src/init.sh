#!/bin/bash

# Supprimer le fichier /boot/config.txt existant
echo "Suppression de /boot/config.txt..."
sudo rm -f /boot/config.txt

# Recréer /boot/config.txt avec le nouveau contenu
echo "Création d'un nouveau /boot/config.txt..."
cat <<'EOF' | sudo tee /boot/config.txt
# For more options and information see
# http://rpf.io/configtxt
# Some settings may impact device functionality. See link above for details

# uncomment if you get no picture on HDMI for a default "safe" mode
#hdmi_safe=1

# uncomment the following to adjust overscan. Use positive numbers if console
# goes off screen, and negative if there is too much border
#overscan_left=16
#overscan_right=16
#overscan_top=16
#overscan_bottom=16

# uncomment to force a console size. By default it will be display's size minus
# overscan.
#framebuffer_width=1280
#framebuffer_height=720

# uncomment if hdmi display is not detected and composite is being output
#hdmi_force_hotplug=1

# uncomment to force a specific HDMI mode (this will force VGA)
#hdmi_group=1
#hdmi_mode=1

# uncomment to force a HDMI mode rather than DVI. This can make audio work in
# DMT (computer monitor) modes
#hdmi_drive=2

# uncomment to increase signal to HDMI, if you have interference, blanking, or
# no display
#config_hdmi_boost=4

# uncomment for composite PAL
#sdtv_mode=2

#uncomment to overclock the arm. 700 MHz is the default.
#arm_freq=800

# Uncomment some or all of these to enable the optional hardware interfaces
#dtparam=i2c_arm=on
#dtparam=i2s=on
#dtparam=spi=on

# Uncomment this to enable infrared communication.
#dtoverlay=gpio-ir,gpio_pin=17
#dtoverlay=gpio-ir-tx,gpio_pin=18

# Additional overlays and parameters are documented /boot/overlays/README

# Enable audio (loads snd_bcm2835)
dtparam=audio=on

# Automatically load overlays for detected cameras
camera_auto_detect=0

# Automatically load overlays for detected DSI displays
display_auto_detect=1

# Enable DRM VC4 V3D driver
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Run in 64-bit mode
arm_64bit=1

# Disable compensation for displays with overscan
disable_overscan=1

[cm4]
# Enable host mode on the 2711 built-in XHCI USB controller.
# This line should be removed if the legacy DWC2 controller is required
# (e.g. for USB device mode) or if USB support is not required.
otg_mode=1

[all]

[pi4]
# Run as fast as firmware / board allows
arm_boost=1

[all]
dtoverlay=imx708
EOF

echo "Nouveau /boot/config.txt créé."

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

