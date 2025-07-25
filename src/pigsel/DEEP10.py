#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SYSTÈME D'ANALYSE DE CARCASSES PORCINES
Version optimisée - Juillet 2024
"""

import os
import math
import time
import cv2
import numpy as np
import tensorflow as tf
import warnings
import json
import threading
from PIL import Image
from termios import TCIOFLUSH, tcflush
from time import strftime, perf_counter
from threading import Thread, Lock
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import keyboard
from gpiozero import Button
from picamera2 import Picamera2, Preview
from libcamera import Transform, controls
from rpi5_ws2812.ws2812 import Color, WS2812SpiDriver
from scipy.signal import savgol_filter
import RPi.GPIO as GPIO

# =====================================================
# CONFIGURATION GÉNÉRALE
# =====================================================
warnings.filterwarnings("ignore", message="The value of the smallest subnormal")

# Constantes d'affichage
SCREEN_SIZE = (800, 480)
CAMERA_RES = (2304, 1296)
PREVIEW_DURATION = 2.0  # Durée d'affichage des résultats en secondes

# Calcul des dimensions de prévisualisation
TARGET_RATIO = SCREEN_SIZE[0] / SCREEN_SIZE[1]
CAMERA_RATIO = CAMERA_RES[0] / CAMERA_RES[1]

if CAMERA_RATIO > TARGET_RATIO:
    SCALED_HEIGHT = SCREEN_SIZE[1]
    SCALED_WIDTH = int(CAMERA_RES[0] * (SCALED_HEIGHT / CAMERA_RES[1]))
else:
    SCALED_WIDTH = SCREEN_SIZE[0]
    SCALED_HEIGHT = int(CAMERA_RES[1] * (SCALED_WIDTH / CAMERA_RES[0]))

X_OFFSET = (SCREEN_SIZE[0] - SCALED_WIDTH) // 2
Y_OFFSET = (SCREEN_SIZE[1] - SCALED_HEIGHT) // 2

# Configuration GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # BP0 - Capture
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # BP1 - Incrémenter
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # BP2 - Décrementer

# Chemins des fichiers
CONFIG_FILE = "/home/unissia/Documents/DEPOTOIR/numero_porc.json"
BASE_DIR = "/home/unissia/Documents/KERMENE_1704"
MODEL_PATH = 'DOUBLE_QUINTOA_1024.tflite'

# Facteur de conversion pixel/mm
PIXEL_TO_MM = 150.0 / 239.0

# Variables globales pour la gestion d'affichage
displaying_result = False
display_lock = Lock()
image_overlay_active = False

# =====================================================
# FONCTIONS D'INITIALISATION
# =====================================================

def initialize_directories():
    """Initialise les répertoires de stockage"""
    abattoir_code = lire_abattoir()
    photos_dir = os.path.join(BASE_DIR, "IMG_ORIGIN", abattoir_code)
    output_dir = os.path.join(BASE_DIR, "RESULTATS", abattoir_code)
    
    for folder in [photos_dir, output_dir]:
        os.makedirs(folder, exist_ok=True)
    
    return photos_dir, output_dir

def initialize_camera():
    """Initialise et configure la caméra"""
    cam = Picamera2()
    preview_config = cam.create_preview_configuration(
        main={"size": CAMERA_RES},
        transform=Transform(vflip=0),
        buffer_count=3
    )
    cam.configure(preview_config)
    cam.start_preview(Preview.QTGL, x=0, y=0, width=SCREEN_SIZE[0], height=SCREEN_SIZE[1])
    cam.start()
    cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": 7})
    return cam

def initialize_leds():
    """Initialise la bande LED"""
    strip = WS2812SpiDriver(spi_bus=0, spi_device=0, led_count=50).get_strip()
    strip.set_all_pixels(Color(145, 125, 50))
    #strip.set_all_pixels(Color(76, 60, 34))
    strip.show()
    return strip

# =====================================================
# FONCTIONS UTILITAIRES
# =====================================================

def lire_numero():
    """Lit le numéro de porc depuis le fichier de configuration"""
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            numero = data.get("numero")
            if isinstance(numero, int) and numero >= 0:
                return numero
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        pass
    return 0

def lire_abattoir():
    """Lit le code de l'abattoir depuis le fichier de configuration"""
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            abattoir = data.get("abattoir")
            if isinstance(abattoir, str):
                return abattoir
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        pass
    return "ab00"

def incrementer_numero_porc():
    """Incrémente le numéro de porc dans le fichier de configuration"""
    try:
        numero = lire_numero() + 1
        with open(CONFIG_FILE, "w") as f:
            json.dump({"numero": numero}, f)
        return numero
    except Exception as e:
        print(f"[ERREUR] Incrémentation échouée : {e}")
        return lire_numero()

def decrementer_numero_porc():
    """Décrémente le numéro de porc dans le fichier de configuration"""
    try:
        numero = lire_numero()
        if numero > 0:
            numero -= 1
            with open(CONFIG_FILE, "w") as f:
                json.dump({"numero": numero}, f)
        return numero
    except Exception as e:
        print(f"[ERREUR] Décrémentation échouée : {e}")
        return lire_numero()

def resize_and_pad(image, target_width, target_height):
    """Redimensionne et remplit une image pour garder les proportions"""
    h, w = image.shape[:2]
    ratio = min(target_width / w, target_height / h)
    new_w = int(w * ratio)
    new_h = int(h * ratio)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    padded = np.zeros((target_height, target_width, image.shape[2]), dtype=np.uint8)
    x = (target_width - new_w) // 2
    y = (target_height - new_h) // 2
    padded[y:y+new_h, x:x+new_w] = resized
    return padded

# =====================================================
# FONCTIONS D'ANALYSE D'IMAGE
# =====================================================

def find_smallest_thickness(top_pts, lower_pts):
    """Trouve l'épaisseur minimale entre deux ensembles de points"""
    min_d, best = 1e4, None
    for tp in top_pts:
        for lp in lower_pts:
            d = math.hypot(tp[0]-lp[0], tp[1]-lp[1])
            if d < min_d:
                min_d, best = d, (tp, lp)
    return min_d, best

def compute_fat_boundaries(mask, image_vis):
    """Calcule les limites du tissu adipeux"""
    ys, xs = np.where(mask==1)
    if xs.size == 0:
        return [], [], None, None, None, None
        
    xmin, xmax = xs.min(), xs.max()
    upper_pts, topLimit_pts = [], []
    diffT = 130
    
    for x in range(xmin, xmax+1):
        yvals = ys[xs==x]
        if yvals.size:
            upper_pts.append((x, int(yvals.min())))
    
    for x, y0 in upper_pts:
        c0 = int(image_vis[0, x, 2])
        layers = 0
        for y in range(image_vis.shape[0]):
            if layers > 1: 
                break
            if abs(int(image_vis[y, x, 2]) - c0) > diffT:
                if layers == 0:
                    topLimit_pts.append((x, y))
                    c0 = int(image_vis[y, x, 2])
                layers += 1
    
    if upper_pts and topLimit_pts:
        d1, (ptT, ptU) = find_smallest_thickness(topLimit_pts, upper_pts)
    else:
        d1, ptT, ptU = None, None, None
    
    coord_ref = max(upper_pts, key=lambda t: t[0]) if upper_pts else None
    return upper_pts, topLimit_pts, coord_ref, d1, ptT, ptU

def extract_top_line(mask):
    """Extrait la ligne supérieure du muscle"""
    ys, xs = np.where(mask==2)
    if xs.size == 0:
        return np.array([]), np.array([])
    
    pts = []
    for x in sorted(np.unique(xs)):
        yvals = ys[xs==x]
        if yvals.size:
            pts.append((x, int(yvals.min())))
    
    arr = np.array(pts)
    return arr[:,0], arr[:,1]

def smooth_boundary_savgol(pts, window=11, poly=2):
    """Lisse une frontière avec le filtre Savitzky-Golay"""
    if not pts:
        return np.array([]), np.array([])
        
    pts = sorted(pts, key=lambda p: p[0])
    x, y = zip(*pts)
    x = np.array(x)
    y = np.array(y, dtype=np.float32)
    xs_full = np.arange(x[0], x[-1]+1)
    y_full = np.interp(xs_full, x, y)
    
    if len(y_full) < window:
        return xs_full, y_full
        
    y_s = savgol_filter(y_full, window, poly)
    return xs_full, y_s

# =====================================================
# CHARGEMENT ET UTILISATION DU MODÈLE
# =====================================================

def load_tflite_model(model_path, num_threads=4):
    """Charge le modèle TFLite"""
    interpreter = tf.lite.Interpreter(
        model_path=model_path,
        num_threads=num_threads
    )
    interpreter.allocate_tensors()
    return interpreter

# Initialisation du modèle
interpreter = load_tflite_model(MODEL_PATH, num_threads=4)
input_details = interpreter.get_input_details()[0]
output_details = interpreter.get_output_details()[0]

# =====================================================
# PIPELINE DE TRAITEMENT D'IMAGE
# =====================================================

def analyze_and_annotate(proc_image, output_path):
    """Effectue l'analyse complète de l'image et génère l'annotation"""
    timing_info = {}
    
    # Préparation de l'image
    start_prep = perf_counter()
    img_bgr = cv2.resize(proc_image, (256, 256))
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    timing_info['image_prep'] = perf_counter() - start_prep

    # Préparation des données d'entrée
    start_model_input = perf_counter()
    input_data = np.expand_dims(img_rgb, axis=0).astype(np.float32)
    
    if input_details['dtype'] in [np.uint8, np.int8]:
        scale, zero_point = input_details['quantization']
        input_data = (input_data / scale + zero_point).astype(input_details['dtype'])
    
    timing_info['model_input_prep'] = perf_counter() - start_model_input

    # Inférence du modèle
    start_inference = perf_counter()
    interpreter.set_tensor(input_details['index'], input_data)
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_details['index'])[0]
    mask = np.argmax(output_data, axis=-1).astype(np.uint8)
    timing_info['inference'] = perf_counter() - start_inference

    # Extraction des caractéristiques
    start_feature_extract = perf_counter()
    upper_pts, topLimit_pts, coord_ref, d1, ptT, ptU = compute_fat_boundaries(mask, img_bgr)
    top_xs, top_ys = extract_top_line(mask)
    timing_info['feature_extract'] = perf_counter() - start_feature_extract

    # Lissage des frontières
    start_smoothing = perf_counter()
    xu1, yu1 = smooth_boundary_savgol(upper_pts)
    xu2, yu2 = smooth_boundary_savgol(topLimit_pts)
    
    if top_xs.size > 0:
        top_xs, top_ys = smooth_boundary_savgol(list(zip(top_xs, top_ys)))
    
    timing_info['smoothing'] = perf_counter() - start_smoothing

    # Calcul des distances
    start_dist_calc = perf_counter()
    d2, pt2 = None, None
    if coord_ref is not None and top_xs.size > 0:
        dists = np.hypot(top_xs - coord_ref[0], top_ys - coord_ref[1])
        min_idx = np.argmin(dists)
        d2 = dists[min_idx]
        pt2 = (int(top_xs[min_idx]), int(top_ys[min_idx]))
    timing_info['distance_calc'] = perf_counter() - start_dist_calc

    # Calcul des mesures
    start_measure_calc = perf_counter()
    G3_mm = d1 * PIXEL_TO_MM if d1 else 0
    M3_mm = d2 * PIXEL_TO_MM if d2 else 0
    TMP = 55.99 - 0.514 * G3_mm + 0.157 * M3_mm
    timing_info['measure_calc'] = perf_counter() - start_measure_calc

    # Création de l'image annotée
    start_annotation = perf_counter()
    scale_factor = 4
    img_highres = cv2.resize(img_bgr, (1024, 1024), interpolation=cv2.INTER_LINEAR)

    # Dessin des éléments
    if xu1.size > 0:
        for i in range(len(xu1) - 1):
            pt1 = (int(xu1[i] * scale_factor), int(yu1[i] * scale_factor))
            pt2_ = (int(xu1[i+1] * scale_factor), int(yu1[i+1] * scale_factor))
            cv2.line(img_highres, pt1, pt2_, (0, 255, 0), 4)

    if xu2.size > 0:
        for i in range(len(xu2) - 1):
            pt1 = (int(xu2[i] * scale_factor), int(yu2[i] * scale_factor))
            pt2_ = (int(xu2[i+1] * scale_factor), int(yu2[i+1] * scale_factor))
            cv2.line(img_highres, pt1, pt2_, (0, 255, 0), 4)

    if ptT and ptU:
        ptT_high = (int(ptT[0] * scale_factor), int(ptT[1] * scale_factor))
        ptU_high = (int(ptU[0] * scale_factor), int(ptU[1] * scale_factor))
        cv2.line(img_highres, ptT_high, ptU_high, (0, 0, 255), 4)

    if top_xs.size > 0:
        for i in range(len(top_xs) - 1):
            pt1 = (int(top_xs[i] * scale_factor), int(top_ys[i] * scale_factor))
            pt2_ = (int(top_xs[i+1] * scale_factor), int(top_ys[i+1] * scale_factor))
            cv2.line(img_highres, pt1, pt2_, (255, 0, 0), 4)

    if coord_ref and pt2:
        coord_ref_high = (int(coord_ref[0] * scale_factor), int(coord_ref[1] * scale_factor))
        pt2_high = (int(pt2[0] * scale_factor), int(pt2[1] * scale_factor))
        cv2.line(img_highres, coord_ref_high, pt2_high, (0, 255, 255), 4)

    # Ajout du texte
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    thickness = 3
    y0 = 60
    cv2.putText(img_highres, f"G3: {G3_mm:.2f}mm", (30, y0), font, font_scale, (0, 0, 255), thickness, cv2.LINE_AA)
    cv2.putText(img_highres, f"M3: {M3_mm:.2f}mm", (30, y0+60), font, font_scale, (0, 255, 255), thickness, cv2.LINE_AA)
    cv2.putText(img_highres, f"TMP: {TMP:.2f}", (30, y0+120), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    timing_info['annotation'] = perf_counter() - start_annotation

    # Sauvegarde du résultat
    start_save = perf_counter()
    cv2.imwrite(output_path, img_highres, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    timing_info['save_result'] = perf_counter() - start_save

    return img_highres, timing_info

def process_image(filename, output_analysis_folder):
    """Traite une image capturée et lance son analyse"""
    timing_info = {}
    start_total = perf_counter()

    try:
        # Chargement de l'image
        start_load = perf_counter()
        with Image.open(filename) as orig_img:
            timing_info['load_image'] = perf_counter() - start_load

            # Recadrage
            start_crop = perf_counter()
            crop_coords = (477, 0, 1773, 1296)
            cropped_img = orig_img.crop(crop_coords)
            timing_info['crop'] = perf_counter() - start_crop

            # Conversion de format
            start_convert = perf_counter()
            img_cv = cv2.cvtColor(np.array(cropped_img), cv2.COLOR_RGB2BGR)
            timing_info['convert_format'] = perf_counter() - start_convert
            
            # Ajout du numéro de porc
            num_porc = lire_numero()
            cv2.putText(img_cv, f"N_Porc : {num_porc}", (10, 475),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)

            # Redimensionnement
            start_resize = perf_counter()
            processed_img = cv2.resize(img_cv, (640, 360))
            timing_info['resize'] = perf_counter() - start_resize

            timing_info['total_process'] = perf_counter() - start_total
            
            # Chemin de sortie
            output_path = os.path.join(output_analysis_folder, f"{num_porc}_{strftime('%Y%m%d')}.jpeg")
            return processed_img, timing_info, output_path
    except Exception as e:
        print(f"Erreur traitement image: {str(e)}")
        return None, {}, ""

# =====================================================
# GESTION DES THREADS ET DES FILES D'ATTENTE
# =====================================================

analysis_queue = Queue(maxsize=3)

def analysis_worker(cam, photos_dir, output_analysis_folder):
    """Thread worker pour le traitement des images"""
    global displaying_result
    
    while True:
        data = analysis_queue.get()
        if data is None:
            break

        filename, capture_time = data
        try:
            # Traitement initial
            start_processing = perf_counter()
            proc_img, process_timing, output_path = process_image(filename, output_analysis_folder)
            
            if proc_img is None:
                continue
                
            process_time = perf_counter() - start_processing

            # Analyse et annotation
            start_analysis = perf_counter()
            annotated_img, analysis_timing = analyze_and_annotate(proc_img, output_path)
            analysis_time = perf_counter() - start_analysis

            # Affichage du résultat
            start_overlay = perf_counter()
            overlay_rgba = cv2.cvtColor(annotated_img, cv2.COLOR_BGR2RGBA)
            overlay_resized = resize_and_pad(overlay_rgba, SCALED_WIDTH, SCALED_HEIGHT)
            
            with display_lock:
                displaying_result = True
                cam.set_overlay(overlay_resized)
            
            # Affichage pendant la durée définie
            time.sleep(PREVIEW_DURATION)
            
            with display_lock:
                displaying_result = False
                cam.set_overlay(None)
            
            overlay_time = perf_counter() - start_overlay

            # Rapport des timings
            print("\n" + "="*50)
            print("RAPPORT DES TEMPS D'EXÉCUTION")
            print("="*50)
            print(f"{'CAPTURE':<20}: {capture_time:.4f}s")
            
            print("\nTRAITEMENT:")
            print("-"*50)
            for step, t in process_timing.items():
                print(f"{step.upper():<20}: {t:.4f}s")
            print(f"{'TOTAL TRAITEMENT':<20}: {process_time:.4f}s")
            
            print("\nANALYSE:")
            print("-"*50)
            for step, t in analysis_timing.items():
                print(f"{step.upper():<20}: {t:.4f}s")
            print(f"{'TOTAL ANALYSE':<20}: {analysis_time:.4f}s")
            
            print("\nAFFICHAGE:")
            print("-"*50)
            print(f"{'OVERLAY':<20}: {overlay_time:.4f}s")
            print("="*50 + "\n")
            
            # Incrémentation après succès
            incrementer_numero_porc()
        except Exception as e:
            print(f"Erreur analyse: {str(e)}")
        finally:
            analysis_queue.task_done()

# =====================================================
# FONCTION PRINCIPALE
# =====================================================

def main():
    """Fonction principale du programme"""
    global displaying_result, image_overlay_active
    
    # Initialisations
    photos_dir, output_analysis_folder = initialize_directories()
    cam = initialize_camera()
    strip = initialize_leds()
    
    # Démarrage du worker d'analyse
    worker_thread = Thread(
        target=analysis_worker, 
        args=(cam, photos_dir, output_analysis_folder),
        daemon=True
    )
    worker_thread.start()
    
    # Pool de threads pour le traitement
    executor = ThreadPoolExecutor(max_workers=2)
    
    try:
        # Variables de contrôle
        last_capture_time = 0
        last_num_update = 0
        num_update_interval = 1.0  # Mise à jour du numéro toutes les secondes
        
        while True:
            current_time = time.monotonic()
            
            # Contrôle manuel de la mise au point
            cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": 7})
            
            # Capture d'image
            if GPIO.input(17) == GPIO.HIGH or keyboard.is_pressed("p"):
                start_capture = perf_counter()
                num_porc = lire_numero()
                filename = os.path.join(photos_dir, f"{num_porc}_{strftime('%Y%m%d')}.jpeg")
                cam.capture_file(filename, format="jpeg", wait=None)
                capture_time = perf_counter() - start_capture
                
                # Ajout à la file d'attente
                analysis_queue.put((filename, capture_time))
                print(f"\nCAPTURE TIME: {capture_time:.4f}s")
                time.sleep(0.2)  # Anti-rebond
            
            # Incrémentation manuelle
            if GPIO.input(27) == GPIO.HIGH:
                print("BP incrémentation manuelle appuyé")
                incrementer_numero_porc()
                time.sleep(0.2)  # Anti-rebond
            
            # Décrémentation manuelle
            if GPIO.input(22) == GPIO.HIGH:
                print("BP décrémentation manuelle appuyé")
                decrementer_numero_porc()
                time.sleep(0.2)  # Anti-rebond
            
            # Affichage du numéro de porc
            with display_lock:
                show_num = not displaying_result
                
            if show_num and (current_time - last_num_update) > num_update_interval:
                num_porc = lire_numero()
                overlay = np.zeros((SCALED_HEIGHT, SCALED_WIDTH, 4), dtype=np.uint8)
                cv2.putText(overlay, f"N_Porc : {num_porc}", (10, SCALED_HEIGHT - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255, 255), 2)
                overlay = cv2.rotate(overlay, cv2.ROTATE_90_COUNTERCLOCKWISE)
                cam.set_overlay(overlay)
                last_num_update = current_time
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur...")
    
    finally:
        # Nettoyage des ressources
        start_cleanup = perf_counter()
        print("\nNettoyage des ressources...")
        
        cam.stop_preview()
        cam.stop()
        cam.close()
        
        executor.shutdown(wait=False)
        analysis_queue.put(None)
        worker_thread.join(timeout=2.0)
        
        strip.set_all_pixels(Color(0, 0, 0))
        strip.show()
        
        try:
            tcflush(0, TCIOFLUSH)
        except Exception as e:
            print(f"[WARN] Impossible de vider le tampon stdin : {e}")
        
        GPIO.cleanup()
        
        cleanup_time = perf_counter() - start_cleanup
        print(f"\nTEMPS DE NETTOYAGE: {cleanup_time:.4f}s")
        print("Arrêt complet du système")

# =====================================================
# POINT D'ENTRÉE PRINCIPAL
# =====================================================

if __name__ == "__main__":
    main()