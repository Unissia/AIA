import RPi.GPIO as GPIO
import tkinter as tk
import json
import time
import os
import subprocess
import sys

# === CONFIGURATION DES BOUTONS ===
BP4 = 23  # Valider
BP5 = 25  # Curseur ←
BP6 = 5   # Incrémenter chiffre

# === GPIO INIT ===
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(BP4, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BP5, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BP6, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# === CONFIGURATION DE L'ÉTAT INITIAL ===
fichier_numero = "/home/unissia/Documents/DEPOTOIR/numero_porc.json"
numero = [0, 0, 0, 0, 0]
abattoir = [0, 0]
curseur = 1  # Position sur chiffre unité (1) pour abattoir, puis passe à 4 pour numéro
mode_abattoir = True
mode_confirmation = False

# === INTERFACE TKINTER ===
root = tk.Tk()
root.title("Saisie Numéro Porc")
root.geometry("480x160")
root.configure(bg="black")

digits = []
abattoir_labels = []

def update_affichage():
    if mode_abattoir:
        for i in range(2):
            abattoir_labels[i].config(text=str(abattoir[i]))
            if i == curseur:
                abattoir_labels[i].config(bg="yellow", fg="black")
            else:
                abattoir_labels[i].config(bg="black", fg="white")
        confirmation_label.config(text="Choix abattoir : BP4 pour valider", fg="orange")
    else:
        for i in range(5):
            digits[i].config(text=str(numero[i]))
            if i == curseur and not mode_confirmation:
                digits[i].config(bg="yellow", fg="black")
            else:
                digits[i].config(bg="black", fg="white")
        confirmation_label.config(text="Valider : BP4" if mode_confirmation else "")

frame_ab = tk.Frame(root, bg="black")
frame_ab.pack(pady=5)
tk.Label(frame_ab, text="ab", font=("Helvetica", 32), width=2, bg="black", fg="white").pack(side=tk.LEFT)
for i in range(2):
    lbl = tk.Label(frame_ab, text="0", font=("Helvetica", 32), width=2, bg="black", fg="white")
    lbl.pack(side=tk.LEFT, padx=2)
    abattoir_labels.append(lbl)

frame = tk.Frame(root, bg="black")
frame.pack(pady=5)
for i in range(5):
    lbl = tk.Label(frame, text="0", font=("Helvetica", 32), width=2, bg="black", fg="white")
    lbl.pack(side=tk.LEFT, padx=2)
    digits.append(lbl)

confirmation_label = tk.Label(root, text="", font=("Helvetica", 16), bg="black")
confirmation_label.pack()

# === SAUVEGARDE DU NUMÉRO EN JSON ===
def sauvegarder_numero():
    numero_final = int("".join(str(d) for d in numero))
    abattoir_str = f"ab{abattoir[0]}{abattoir[1]}"
    os.makedirs(os.path.dirname(fichier_numero), exist_ok=True)
    with open(fichier_numero, "w") as f:
        json.dump({"abattoir": abattoir_str, "numero": numero_final}, f)
    print(f"[INFO] {abattoir_str} - Numéro {numero_final:05d} enregistré")
    root.destroy()

# === LECTURE DES BOUTONS ===
def verifier_boutons():
    global curseur, mode_confirmation, mode_abattoir

    try:
        if GPIO.input(BP5) == GPIO.HIGH:
            if mode_abattoir:
                curseur = (curseur - 1) % 2
            elif not mode_confirmation:
                curseur = (curseur - 1) % 5
            else:
                mode_confirmation = False
            update_affichage()
            time.sleep(0.3)

        if GPIO.input(BP6) == GPIO.HIGH:
            if mode_abattoir:
                abattoir[curseur] = (abattoir[curseur] + 1) % 10
            elif not mode_confirmation:
                numero[curseur] = (numero[curseur] + 1) % 10
            update_affichage()
            time.sleep(0.3)

        if GPIO.input(BP4) == GPIO.HIGH:
            if mode_abattoir:
                mode_abattoir = False
                curseur = 4
            elif not mode_confirmation:
                mode_confirmation = True
            else:
                sauvegarder_numero()
                time.sleep(0.3)
                os.system("python3 /home/unissia/Documents/DEPOTOIR/TEST_IA/IA_FINAL102.py")
            update_affichage()
            time.sleep(0.3)

    except RuntimeError as e:
        print("[ERREUR GPIO] :", e)

    root.after(100, verifier_boutons)

# === LANCEMENT INTERFACE ===
update_affichage()
root.after(100, verifier_boutons)

try:
    root.mainloop()
finally:
    GPIO.cleanup()
