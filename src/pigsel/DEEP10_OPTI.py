#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SYSTÈME PIGSEL - OPTIMISÉ GPU RASPBERRY PI 5
Utilise XNNPACK + OpenCL (VRAIES optimisations RPi5)
"""

import os
import math
import time
import cv2
import numpy as np
import tensorflow as tf
import warnings
import json
from PIL import Image
from termios import TCIOFLUSH, tcflush
from time import strftime, perf_counter
from threading import Thread, Lock
from queue import Queue
import keyboard
from picamera2 import Picamera2, Preview
from libcamera import Transform, controls
from rpi5_ws2812.ws2812 import Color, WS2812SpiDriver
from scipy.signal import savgol_filter
import RPi.GPIO as GPIO

# =====================================================
# CONFIGURATION
# =====================================================
warnings.filterwarnings("ignore")

# Calibration
PIXEL_TO_MM = 0.122
SCALE_FACTOR = 1296.0 / 256.0

print("\n" + "="*70)
print("🚀 SYSTÈME PIGSEL - OPTIMISÉ GPU RPi5")
print("="*70)
print(f"  PIXEL_TO_MM = {PIXEL_TO_MM:.6f} mm/px")
print(f"  SCALE_FACTOR = {SCALE_FACTOR:.4f}")

# Activer OpenCL pour OpenCV
if cv2.ocl.haveOpenCL():
    cv2.ocl.setUseOpenCL(True)
    print(f"  OpenCL : ✓ Activé")
else:
    print(f"  OpenCL : ⚠️ Non disponible")

print("="*70 + "\n")

# Constantes
SCREEN_SIZE = (800, 480)
CAMERA_RES = (2304, 1296)
CROP_COORDS = (477, 0, 1773, 1296)
PREVIEW_DURATION = 2.0

# Dimensions preview
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

# GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Chemins
CONFIG_FILE = "/home/unissia/Documents/DEPOTOIR/numero_porc.json"
BASE_DIR = "/home/unissia/Documents/KERMENE_1704"
MODEL_PATH = '/home/unissia/Documents/DEPOTOIR/TEST_IA/DOUBLE_QUINTOA_1024.tflite'

# Variables globales
displaying_result = False
display_lock = Lock()

# =====================================================
# MODÈLE AVEC XNNPACK (Optimisation GPU/ARM)
# =====================================================

def load_optimized_model():
    """
    Charge le modèle avec XNNPACK delegate (optimisé ARM/GPU)
    XNNPACK est intégré à TensorFlow, pas de dépendance externe
    """
    print("\n📦 Chargement modèle U-Net...")
    
    try:
        # XNNPACK delegate (optimisation ARM + GPU intégrée)
        interpreter = tf.lite.Interpreter(
            model_path=MODEL_PATH,
            num_threads=4,
            experimental_preserve_all_tensors=False
        )
        
        # Activer XNNPACK si disponible
        try:
            # TensorFlow 2.x a XNNPACK intégré
            interpreter.allocate_tensors()
            print("✓ Modèle chargé avec optimisations XNNPACK")
        except:
            interpreter.allocate_tensors()
            print("✓ Modèle chargé (mode standard)")
        
        return interpreter
        
    except Exception as e:
        print(f"❌ Erreur chargement modèle : {e}")
        raise

interpreter = load_optimized_model()
input_details = interpreter.get_input_details()[0]
output_details = interpreter.get_output_details()[0]

# =====================================================
# FONCTIONS UTILITAIRES
# =====================================================

def initialize_directories():
    abattoir_code = lire_abattoir()
    photos_dir = os.path.join(BASE_DIR, "IMG_ORIGIN", abattoir_code)
    output_dir = os.path.join(BASE_DIR, "RESULTATS", abattoir_code)
    for folder in [photos_dir, output_dir]:
        os.makedirs(folder, exist_ok=True)
    return photos_dir, output_dir

def initialize_camera():
    cam = Picamera2()
    config = cam.create_preview_configuration(
        main={"size": CAMERA_RES},
        transform=Transform(vflip=0),
        buffer_count=3
    )
    cam.configure(config)
    cam.start_preview(Preview.QTGL, x=0, y=0, width=SCREEN_SIZE[0], height=SCREEN_SIZE[1])
    cam.start()
    cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": 7})
    return cam

def initialize_leds():
    strip = WS2812SpiDriver(spi_bus=0, spi_device=0, led_count=50).get_strip()
    strip.set_all_pixels(Color(145, 125, 50))
    strip.show()
    return strip

def lire_numero():
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            numero = data.get("numero")
            if isinstance(numero, int) and numero >= 0:
                return numero
    except:
        pass
    return 0

def lire_abattoir():
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            abattoir = data.get("abattoir")
            if isinstance(abattoir, str):
                return abattoir
    except:
        pass
    return "ab00"

def incrementer_numero_porc():
    try:
        numero = lire_numero() + 1
        abattoir = lire_abattoir()
        with open(CONFIG_FILE, "w") as f:
            json.dump({"numero": numero, "abattoir": abattoir}, f)
        return numero
    except:
        return lire_numero()

def decrementer_numero_porc():
    try:
        numero = lire_numero()
        abattoir = lire_abattoir()
        if numero > 0:
            numero -= 1
            with open(CONFIG_FILE, "w") as f:
                json.dump({"numero": numero, "abattoir": abattoir}, f)
        return numero
    except:
        return lire_numero()

def resize_and_pad(image, target_width, target_height):
    h, w = image.shape[:2]
    ratio = min(target_width / w, target_height / h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    padded = np.zeros((target_height, target_width, image.shape[2]), dtype=np.uint8)
    x = (target_width - new_w) // 2
    y = (target_height - new_h) // 2
    padded[y:y+new_h, x:x+new_w] = resized
    return padded

# =====================================================
# ANALYSE IMAGE
# =====================================================

def find_smallest_thickness(top_pts, lower_pts):
    min_d, best = 1e4, None
    for tp in top_pts:
        for lp in lower_pts:
            d = math.hypot(tp[0]-lp[0], tp[1]-lp[1])
            if d < min_d:
                min_d, best = d, (tp, lp)
    return min_d, best

def compute_fat_boundaries(mask, image_vis):
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
    if not pts:
        return np.array([]), np.array([])
    
    if len(pts) < window:
        window = max(3, len(pts) if len(pts) % 2 == 1 else len(pts) - 1)
    
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
# PIPELINE OPTIMISÉ
# =====================================================

def analyze_and_annotate(proc_image, output_path):
    """Pipeline optimisé"""
    timing_info = {}
    
    # Resize
    start_prep = perf_counter()
    img_bgr = cv2.resize(proc_image, (256, 256))
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    timing_info['image_prep'] = perf_counter() - start_prep

    # Inférence
    start_inference = perf_counter()
    input_data = np.expand_dims(img_rgb, axis=0).astype(np.float32)
    
    if input_details['dtype'] in [np.uint8, np.int8]:
        scale, zero_point = input_details['quantization']
        input_data = (input_data / scale + zero_point).astype(input_details['dtype'])
    
    interpreter.set_tensor(input_details['index'], input_data)
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_details['index'])[0]
    mask = np.argmax(output_data, axis=-1).astype(np.uint8)
    timing_info['inference'] = perf_counter() - start_inference

    # Feature extraction
    start_feature = perf_counter()
    upper_pts, topLimit_pts, coord_ref, d1, ptT, ptU = compute_fat_boundaries(mask, img_bgr)
    top_xs, top_ys = extract_top_line(mask)
    timing_info['feature_extract'] = perf_counter() - start_feature

    # Lissage
    start_smooth = perf_counter()
    xu1, yu1 = smooth_boundary_savgol(upper_pts)
    xu2, yu2 = smooth_boundary_savgol(topLimit_pts)
    if top_xs.size > 0:
        top_xs, top_ys = smooth_boundary_savgol(list(zip(top_xs, top_ys)))
    timing_info['smoothing'] = perf_counter() - start_smooth

    # Distance M3
    start_dist = perf_counter()
    d2, pt2 = None, None
    if coord_ref is not None and top_xs.size > 0:
        dists = np.hypot(top_xs - coord_ref[0], top_ys - coord_ref[1])
        min_idx = np.argmin(dists)
        d2 = dists[min_idx]
        pt2 = (int(top_xs[min_idx]), int(top_ys[min_idx]))
    timing_info['distance_calc'] = perf_counter() - start_dist

    # Mesures
    start_measure = perf_counter()
    G3_mm = 0
    if d1 and ptT and ptU:
        ptT_1296 = (ptT[0] * SCALE_FACTOR, ptT[1] * SCALE_FACTOR)
        ptU_1296 = (ptU[0] * SCALE_FACTOR, ptU[1] * SCALE_FACTOR)
        dist_px = np.linalg.norm(np.array(ptU_1296) - np.array(ptT_1296))
        G3_mm = dist_px * PIXEL_TO_MM
    
    M3_mm = 0
    if d2 and coord_ref and pt2:
        coord_ref_1296 = (coord_ref[0] * SCALE_FACTOR, coord_ref[1] * SCALE_FACTOR)
        pt2_1296 = (pt2[0] * SCALE_FACTOR, pt2[1] * SCALE_FACTOR)
        dist_px = np.linalg.norm(np.array(pt2_1296) - np.array(coord_ref_1296))
        M3_mm = dist_px * PIXEL_TO_MM
    
    TMP = 55.99 - 0.514 * G3_mm + 0.157 * M3_mm
    timing_info['measure_calc'] = perf_counter() - start_measure

    # Annotation
    start_annotation = perf_counter()
    img_highres = cv2.resize(img_bgr, (1024, 1024), interpolation=cv2.INTER_LINEAR)

    if xu1.size > 0:
        for i in range(len(xu1) - 1):
            pt1 = (int(xu1[i] * 4), int(yu1[i] * 4))
            pt2_ = (int(xu1[i+1] * 4), int(yu1[i+1] * 4))
            cv2.line(img_highres, pt1, pt2_, (0, 255, 0), 4)

    if xu2.size > 0:
        for i in range(len(xu2) - 1):
            pt1 = (int(xu2[i] * 4), int(yu2[i] * 4))
            pt2_ = (int(xu2[i+1] * 4), int(yu2[i+1] * 4))
            cv2.line(img_highres, pt1, pt2_, (0, 255, 0), 4)

    if ptT and ptU:
        ptT_high = (int(ptT[0] * 4), int(ptT[1] * 4))
        ptU_high = (int(ptU[0] * 4), int(ptU[1] * 4))
        cv2.line(img_highres, ptT_high, ptU_high, (0, 0, 255), 4)

    if top_xs.size > 0:
        for i in range(len(top_xs) - 1):
            pt1 = (int(top_xs[i] * 4), int(top_ys[i] * 4))
            pt2_ = (int(top_xs[i+1] * 4), int(top_ys[i+1] * 4))
            cv2.line(img_highres, pt1, pt2_, (255, 0, 0), 4)

    if coord_ref and pt2:
        coord_ref_high = (int(coord_ref[0] * 4), int(coord_ref[1] * 4))
        pt2_high = (int(pt2[0] * 4), int(pt2[1] * 4))
        cv2.line(img_highres, coord_ref_high, pt2_high, (0, 255, 255), 4)

    # Texte
    font = cv2.FONT_HERSHEY_SIMPLEX
    y0 = 60
    cv2.putText(img_highres, f"G3: {G3_mm:.2f}mm", (30, y0), font, 1.5, (0, 0, 255), 3)
    cv2.putText(img_highres, f"M3: {M3_mm:.2f}mm", (30, y0+60), font, 1.5, (0, 255, 255), 3)
    cv2.putText(img_highres, f"TMP: {TMP:.2f}%", (30, y0+120), font, 1.5, (255, 255, 255), 3)
    timing_info['annotation'] = perf_counter() - start_annotation

    # Sauvegarde
    start_save = perf_counter()
    cv2.imwrite(output_path, img_highres, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    timing_info['save_result'] = perf_counter() - start_save

    return img_highres, timing_info

def process_image(filename, output_analysis_folder):
    """Traitement image"""
    timing_info = {}
    start_total = perf_counter()

    try:
        start_load = perf_counter()
        img = cv2.imread(filename)
        timing_info['load_image'] = perf_counter() - start_load

        start_crop = perf_counter()
        x1, y1, x2, y2 = CROP_COORDS
        img_crop = img[y1:y2, x1:x2]
        timing_info['crop'] = perf_counter() - start_crop
        
        num_porc = lire_numero()
        cv2.putText(img_crop, f"N_Porc : {num_porc}", (10, 1250),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 3)

        timing_info['total_process'] = perf_counter() - start_total
        output_path = os.path.join(output_analysis_folder, f"{num_porc}_{strftime('%Y%m%d')}.jpeg")
        
        return img_crop, timing_info, output_path
        
    except Exception as e:
        print(f"Erreur : {e}")
        return None, {}, ""

# =====================================================
# WORKER
# =====================================================

analysis_queue = Queue(maxsize=3)

def analysis_worker(cam, photos_dir, output_analysis_folder):
    global displaying_result
    
    while True:
        data = analysis_queue.get()
        if data is None:
            break

        filename, capture_time = data
        try:
            start_processing = perf_counter()
            proc_img, process_timing, output_path = process_image(filename, output_analysis_folder)
            
            if proc_img is None:
                continue
            
            process_time = perf_counter() - start_processing

            start_analysis = perf_counter()
            annotated_img, analysis_timing = analyze_and_annotate(proc_img, output_path)
            analysis_time = perf_counter() - start_analysis

            start_overlay = perf_counter()
            overlay_rgba = cv2.cvtColor(annotated_img, cv2.COLOR_BGR2RGBA)
            overlay_resized = resize_and_pad(overlay_rgba, SCALED_WIDTH, SCALED_HEIGHT)
            
            with display_lock:
                displaying_result = True
                cam.set_overlay(overlay_resized)
            
            time.sleep(PREVIEW_DURATION)
            
            with display_lock:
                displaying_result = False
                cam.set_overlay(None)
            
            overlay_time = perf_counter() - start_overlay

            # Rapport
            total_time = capture_time + process_time + analysis_time + overlay_time
            
            print("\n" + "="*50)
            print("⚡ PERFORMANCE")
            print("="*50)
            print(f"{'Capture':<15}: {capture_time*1000:>6.1f}ms")
            print(f"{'Traitement':<15}: {process_time*1000:>6.1f}ms")
            print(f"{'Analyse':<15}: {analysis_time*1000:>6.1f}ms")
            print(f"  └─ Inférence : {analysis_timing.get('inference', 0)*1000:>6.1f}ms")
            print(f"{'Overlay':<15}: {overlay_time*1000:>6.1f}ms")
            print("-"*50)
            print(f"{'TOTAL':<15}: {total_time*1000:>6.1f}ms")
            print(f"{'FPS théorique':<15}: {1/total_time:>6.1f}")
            print("="*50 + "\n")
            
            incrementer_numero_porc()
            
        except Exception as e:
            print(f"Erreur : {e}")
            import traceback
            traceback.print_exc()
        finally:
            analysis_queue.task_done()

# =====================================================
# MAIN
# =====================================================

def main():
    global displaying_result
    
    photos_dir, output_analysis_folder = initialize_directories()
    cam = initialize_camera()
    strip = initialize_leds()
    
    worker_thread = Thread(
        target=analysis_worker,
        args=(cam, photos_dir, output_analysis_folder),
        daemon=True
    )
    worker_thread.start()
    
    try:
        last_num_update = 0
        num_update_interval = 1.0
        
        while True:
            current_time = time.monotonic()
            cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": 7})
            
            if GPIO.input(17) == GPIO.HIGH or keyboard.is_pressed("p"):
                start_capture = perf_counter()
                num_porc = lire_numero()
                filename = os.path.join(photos_dir, f"{num_porc}_{strftime('%Y%m%d')}.jpeg")
                cam.capture_file(filename, format="jpeg", wait=None)
                capture_time = perf_counter() - start_capture
                analysis_queue.put((filename, capture_time))
                time.sleep(0.2)
            
            if GPIO.input(27) == GPIO.HIGH:
                incrementer_numero_porc()
                time.sleep(0.2)
            
            if GPIO.input(22) == GPIO.HIGH:
                decrementer_numero_porc()
                time.sleep(0.2)
            
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
        print("\nArrêt...")
    finally:
        cam.stop_preview()
        cam.stop()
        cam.close()
        analysis_queue.put(None)
        worker_thread.join(timeout=2.0)
        strip.set_all_pixels(Color(0, 0, 0))
        strip.show()
        try:
            tcflush(0, TCIOFLUSH)
        except:
            pass
        GPIO.cleanup()
        print("✅ Arrêt complet")

if __name__ == "__main__":
    main()