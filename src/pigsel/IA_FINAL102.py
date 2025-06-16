import os
import math
import time
import cv2
import numpy as np
import tensorflow as tf
import warnings
import RPi.GPIO as GPIO
import json


from PIL import Image
from sys import stdin
from termios import TCIOFLUSH, tcflush
from time import strftime, perf_counter
from threading import Thread
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from picamera2 import Picamera2, Preview
from libcamera import Transform, controls
from rpi5_ws2812.ws2812 import Color, WS2812SpiDriver
##########################
# Config pour les nouvelles LED
#from rpi_ws281x import PixelStrip, Color
##########################

warnings.filterwarnings("ignore", message="The value of the smallest subnormal")



# =====================================================
# CONFIGURATION DE LA PREVIEW
# =====================================================
image_overlay_active = False

screen_width, screen_height = 800, 480
#screen_width, screen_height = 2304, 1296
camera_width, camera_height = 2304, 1296
#camera_width, camera_height = 800, 480

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

# =====================================================
# CONFIGURATION DES LEDS & BOUTONS
# =====================================================
# === Configuration GPIO avec RPi.GPIO ===
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  #BP0
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  #BP1 ---> Incrémenter
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  #BP2 --> Décrementer
#GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  #BP3

BTP_CAPTURE = 17  # Bouton de capture
BTP_QUIT    = 24  # Bouton de sortie

# declaration des led
strip = WS2812SpiDriver(spi_bus=0, spi_device=0, led_count=50).get_strip()


# Allumer les LED en continu dès le lancement avec la couleur désirée
strip.set_all_pixels(Color(76, 60, 34))
strip.show()
#############################
# Config pour les nouvelles LED


#############################


# =====================================================
# INITIALISATION DE LA CAMÉRA
# =====================================================
cam = Picamera2()

preview_config = cam.create_preview_configuration(
    main={"size": (camera_width, camera_height)},
    #main={"size": (camera_height, camera_width)},
    transform=Transform(vflip=1, hflip=1, rotation=180),
    #transform=Transform(rotation=-180),
    buffer_count=2
)

cam.configure(preview_config)
screen_width, screen_height = 2304, 1296  # ou celles de ton écran
cam.start_preview(Preview.QTGL, x=0, y=0, width=screen_width, height=screen_height)
#cam.start_preview(Preview.QTGL, x=x_offset, y=y_offset, width=scaled_width, heigth=scaled_heigth)
#cam.start_preview(Preview.QTGL)
cam.start()
DIST = 7  # Focus manuel


# ================================================
# Fonction pour lire le numero de la carcasse dans le fichier .json
# ====================================================

def lire_numero():
    chemin = "/home/unissia/Documents/DEPOTOIR/numero_porc.json"
    try:
        with open(chemin, "r") as f:
            data = json.load(f)
            numero = data.get("numero")
            if isinstance(numero, int) and numero >= 0:
                return numero
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        pass
    return 0

def lire_abattoir():
    chemin = "/home/unissia/Documents/DEPOTOIR/numero_porc.json"
    try:
        with open(chemin, "r") as f:
            data = json.load(f)
            abattoir = data.get("abattoir")
            if isinstance(abattoir, str):
                return abattoir
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        pass
    return "ab00"

numero_porc = lire_numero()
warnings.filterwarnings("ignore", message="The value of the smallest subnormal")

# =====================================================
# CONFIGURATION DES DOSSIERS
# =====================================================
abattoir_code = lire_abattoir()
base_dir = "/home/unissia/Documents/KERMENE_1704"
photos_dir = os.path.join(base_dir, "IMG_ORIGIN", abattoir_code)
final_dir = os.path.join(photos_dir, "processed")
output_analysis_folder = os.path.join(base_dir, "RESULTATS", abattoir_code)

for folder in [photos_dir, final_dir, output_analysis_folder]:
    if not os.path.exists(folder):
        os.makedirs(folder)

for folder in [photos_dir, final_dir, output_analysis_folder]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# =================================================
# Fonction pour gérer l'incrémentation
# =================================================
def incrementer_numero_porc():
    try:
        numero = lire_numero() + 1
        with open("/home/unissia/Documents/DEPOTOIR/numero_porc.json", "w") as f:
            json.dump({"numero": numero}, f)
        return numero
    except Exception as e:
        print(f"[ERREUR] Incrémentation échouée : {e}")
        return lire_numero()

# =================================================
# Fonction pour gérer la décrémentation
# =================================================
def decrementer_numero_porc():
    try:
        numero = lire_numero()
        if numero > 0:
            numero -= 1
            with open("/home/unissia/Documents/DEPOTOIR/numero_porc.json", "w") as f:
                json.dump({"numero": numero}, f)
        return numero
    except Exception as e:
        print(f"[ERREUR] Décrémentation échouée : {e}")
        return lire_numero()

# =====================================================
# FONCTIONS POUR OVERLAY & PADDING
# =====================================================
def add_padding(image, target_width, target_height):
    h = 636
    w = 636
    delta_w = target_width - w
    delta_h = target_height - h
    top = delta_h // 2 if delta_h > 0 else 0
    bottom = delta_h - top if delta_h > 0 else 0
    left = delta_w // 2 if delta_w > 0 else 0
    right = delta_w - left if delta_w > 0 else 0
    padded = cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0, 255])
    return padded

def clear_overlay():
    transparent = np.zeros((scaled_height, scaled_width, 4), dtype=np.uint8)
    cam.set_overlay(transparent)

clear_overlay()

# =====================================================
# CHARGEMENT DES MODÈLES TFLITE
# =====================================================
def load_tflite_model(model_path, num_threads=4):
    interpreter = tf.lite.Interpreter(model_path=model_path, num_threads=num_threads)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    return interpreter, input_details, output_details

model_path1 = '/home/unissia/Documents/DEPOTOIR/TEST_IA/MEILLEUR_LEGER_365MS.tflite'
model_path2 = '/home/unissia/Documents/DEPOTOIR/TEST_IA/LIGHT_COL.tflite'
interpreter1, input_details1, _ = load_tflite_model(model_path1, num_threads=4)
interpreter2, input_details2, output_details2 = load_tflite_model(model_path2, num_threads=4)

# =====================================================
# FONCTIONS DE PRÉTRAITEMENT
# =====================================================
def crop_image_from_memory(image, crop_coords):
    return image.crop(crop_coords)

def resize_image_cv(image, new_width=None, new_height=None):
    if new_width is None and new_height is None:
        return image
    elif new_width is None:
        ratio = new_height / image.shape[0]
        new_width = int(image.shape[1] * ratio)
    elif new_height is None:
        ratio = new_width / image.shape[1]
        new_height = int(image.shape[0] * ratio)
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)



# =====================================================
# FONCTIONS D'ANALYSE ET D'ANNOTATION
# =====================================================
def FindSmallestThickness(topLimit, lower_boundary):
    top = np.array(topLimit)
    lower = np.array(lower_boundary)
    diff = top[:, None, :] - lower[None, :, :]
    dists = np.sqrt(np.sum(diff**2, axis=2))
    idx = np.unravel_index(np.argmin(dists, axis=None), dists.shape)
    return dists[idx], [tuple(top[idx[0]]), tuple(lower[idx[1]])]

def predict_top_line(interpreter, input_details, output_details, img_input, threshold=0.5):
    input_dtype = input_details[0]['dtype']
    quant_params = input_details[0]['quantization']
    input_data = img_input.copy()
    if input_dtype in [np.int8, np.uint8]:
        scale, zero_point = quant_params
        input_data = input_data / scale + zero_point
        input_data = input_data.astype(input_dtype)
    else:
        input_data = input_data.astype(np.float32)
    interpreter.set_tensor(input_details[0]['index'], input_data)
    start_inf = time.time()
    interpreter.invoke()
    inference_time = time.time() - start_inf
    output_data = interpreter.get_tensor(output_details[0]['index'])
    predicted_mask = np.squeeze(output_data)
    binary_mask = (predicted_mask > threshold).astype(np.uint8)
    if np.sum(binary_mask) == 0:
        return None, None, binary_mask, inference_time
    cols = np.where(np.sum(binary_mask, axis=0) > 0)[0]
    xmin, xmax = int(np.min(cols)), int(np.max(cols))
    sub_mask = binary_mask[:, xmin:xmax+1]
    y_candidates = np.argmax(sub_mask, axis=0)
    valid = np.sum(sub_mask, axis=0) > 0
    x_line = np.arange(xmin, xmax+1)[valid]
    y_line = y_candidates[valid]
    return x_line.tolist(), y_line.tolist(), binary_mask, inference_time

def MeasureFatThickness(image, interpreter):
    img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    img_resized = cv2.resize(img_rgb, (256, 256))
    img_input = np.expand_dims(img_resized.astype(np.float32) / 255.0, axis=0)
    inp_details = interpreter.get_input_details()
    out_details = interpreter.get_output_details()
    input_dtype = inp_details[0]['dtype']
    quant_params = inp_details[0]['quantization']
    input_data = img_input.copy()
    if input_dtype in [np.int8, np.uint8]:
        scale, zero_point = quant_params
        input_data = input_data / scale + zero_point
        input_data = input_data.astype(input_dtype)
    else:
        input_data = input_data.astype(np.float32)
    interpreter.set_tensor(inp_details[0]['index'], input_data)
    interpreter.invoke()
    output_data = interpreter.get_tensor(out_details[0]['index'])
    predicted_mask = np.squeeze(output_data)
    predicted_mask = (predicted_mask > 0.5).astype(np.uint8)
    pts = np.where(predicted_mask == 1)
    coord_gluteus, lower_boundary = None, []
    if pts[0].size > 0:
        xmin, xmax = int(np.min(pts[1])), int(np.max(pts[1]))
        idx = np.argmax(pts[1])
        y_for_xmax = int(pts[0][idx])
        coord_gluteus = (xmax, y_for_xmax)
        for x in range(xmin, xmax+1):
            y_vals = pts[0][pts[1] == x]
            if y_vals.size:
                y_min = int(np.min(y_vals))
                lower_boundary.append((x, y_min))
                image[y_min, x] = [0, 255, 0]
    topLimit = []
    if pts[0].size > 0:
        diffThreshold = 70
        for x in range(xmin, xmax+1):
            color = int(image[0, x, 2])
            layers = 0
            for y in range(image.shape[0]):
                if layers > 1:
                    break
                if abs(int(image[y, x, 2]) - color) > diffThreshold:
                    if layers == 0:
                        topLimit.append((x, y))
                        color = int(image[y, x, 2])
                        image[y, x] = [0, 255, 0]
                    layers += 1
    distance, cords = None, None
    if topLimit and lower_boundary:
        distance, cords = FindSmallestThickness(topLimit, lower_boundary)
        if cords:
            cv2.line(image, cords[0], cords[1], (0, 0, 255), 1)
    return image, coord_gluteus, distance

# Variable globale pour mesurer le temps depuis l'appui sur le bouton
start_capture_time = None

def analyze_and_annotate(proc_image):
    global start_capture_time
    IMG_WIDTH, IMG_HEIGHT = 256, 256
    image = cv2.resize(proc_image, (IMG_WIDTH, IMG_HEIGHT))

    # Modèle 1 : mesure de la zone graisseuse
    imageFat, coord_gluteus, distance_fat = MeasureFatThickness(image.copy(), interpreter1)

    # Modèle 2 : prédiction de la ligne
    img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    img_input = np.expand_dims(cv2.resize(img_rgb, (IMG_WIDTH, IMG_HEIGHT)).astype(np.float32) / 255.0, axis=0)
    x_line2, y_line2, _, _ = predict_top_line(interpreter2, input_details2, output_details2, img_input, threshold=0.5)
    distance_line = None
    if x_line2 is not None and coord_gluteus:
        distances = [math.hypot(x - coord_gluteus[0], y - coord_gluteus[1]) for x, y in zip(x_line2, y_line2)]
        if distances:
            idx_min = int(np.argmin(distances))
            distance_line = distances[idx_min]
            min_point = (x_line2[idx_min], y_line2[idx_min])
            cv2.line(imageFat, coord_gluteus, min_point, (0, 255, 255), 1)
            for i in range(len(x_line2)-1):
                cv2.line(imageFat, (x_line2[i], y_line2[i]), (x_line2[i+1], y_line2[i+1]), (255, 0, 0), 1)

    G3_mm = distance_fat * 0.615 if distance_fat is not None else None
    M3_mm = distance_line * 0.615 if distance_line is not None else None

    if G3_mm is not None and M3_mm is not None:
        #tmp = 62.19 - (0.729 * G3_mm) + (0.144 * M3_mm)
        tmp = 55.99 - (0.514 * G3_mm ) + (0.157 * M3_mm)
    else:
        tmp = None

    # Ajout des textes en haut à gauche
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.35
    thickness = 0
    text_color2 = (0, 0, 255)
    text_color1 = (0, 255, 255)
    text_color3 = (0, 0, 255)
    y0 = 20

    #txt1 = f"G3: {distance_fat:.1f} px" if distance_fat is not None else "G2: n/a"
    #txt2 = f"M3: {distance_line:.1f} px" if distance_line is not None else "M2: n/a"
    txt1 = f"G3: {G3_mm:.1f}mm" if distance_fat is not None else "G3: n/a"
    txt2 = f"M3: {M3_mm:.1f}mm" if distance_line is not None else "M3: n/a"
    txt3 = f"TMP:{tmp:.1f}%" if tmp is not None else "TMP: n/a"

    #cv2.putText(imageFat, txt1, (10, y0), font, font_scale, text_color2, thickness, cv2.LINE_AA)
    #cv2.putText(imageFat, txt2, (125, y0), font, font_scale, text_color1, thickness, cv2.LINE_AA)
    cv2.putText(imageFat, txt1, (5, y0), font, font_scale, text_color2, thickness, cv2.LINE_AA)
    cv2.putText(imageFat, txt2, (90, y0), font, font_scale, text_color1, thickness, cv2.LINE_AA)
    cv2.putText(imageFat, txt3, (175, y0), font, font_scale, text_color3, thickness, cv2.LINE_AA)

    # Mise à l'échelle finale à 1296x1296 pour l'overlay (remplacé ici par 1024x1024 si nécessaire)
    final_image = cv2.resize(imageFat, (1024, 1024), interpolation=cv2.INTER_LINEAR)

    if start_capture_time is not None:
        elapsed_total = perf_counter() - start_capture_time
        print(f"Temps de traitement total: {elapsed_total:.3f} sec", flush=True)
        start_capture_time = None
    num_porc = lire_numero()
    output_path = os.path.join(output_analysis_folder, f"analyzed_{num_porc}_{strftime('%Y%m%d')}.png")
    cv2.imwrite(output_path, final_image)
    return final_image, imageFat



# =====================================================
# PIPELINE MULTITHREAD POUR LE TRAITEMENT
# =====================================================
analysis_queue = Queue()

def process_image(filename):
    crop_coordinates = (477, 0, 1773, 1296)
    try:
        orig_img = Image.open(filename)
    except Exception:
        return

    # Recadrer et convertir en image OpenCV
    cropped_img = crop_image_from_memory(orig_img, crop_coordinates)
    img_cv = cv2.cvtColor(np.array(cropped_img), cv2.COLOR_RGB2BGR)
    #transform=Transform(vflip=0)

    # Ajouter le numéro de porc

    num_porc = lire_numero()
    cv2.putText(img_cv, f"N_Porc : {num_porc}", (10, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

    # Redimensionner et envoyer dans la file d’analyse
    processed_img = resize_image_cv(img_cv, new_width=256)
    analysis_queue.put(processed_img)



def analysis_worker():
    global image_overlay_active
    while True:
        proc_img = analysis_queue.get()
        if proc_img is None:
            break
        annotated_image, imageFat = analyze_and_annotate(proc_img)
        overlay = cv2.cvtColor(imageFat, cv2.COLOR_BGR2RGBA)
        overlay = cv2.rotate(overlay, cv2.ROTATE_90_COUNTERCLOCKWISE)
        overlay = add_padding(overlay, 853, 480)

        cam.set_overlay(overlay)
        image_overlay_active = True
        time.sleep(2)
        clear_overlay()
        image_overlay_active = False
        analysis_queue.task_done()
        incrementer_numero_porc()


analysis_thread = Thread(target=analysis_worker, daemon=True)
analysis_thread.start()

executor = ThreadPoolExecutor(max_workers=2)

# =====================================================
# BOUCLE PRINCIPALE DE CAPTURE
# =====================================================
try:
    while True:
        time.sleep(0.1)
        cam.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": DIST})

        if GPIO.input(17) == GPIO.HIGH:
            start_capture_time = perf_counter()
            num_porc = lire_numero()
            filename = os.path.join(photos_dir, f"{num_porc}_{strftime('%Y%m%d')}.png")
            cam.capture_file(filename, format="png", wait=None)
            transform=Transform(vflip=1)

            # Ajout du numéro de porc sur l'image capturée
            img = cv2.imread(filename)
            num_porc = lire_numero()
            cv2.putText(img, f"N_Porc : {num_porc}", (10, 475),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            cv2.imwrite(filename, img)

            time.sleep(0.05)
            executor.submit(process_image, filename)
            #incrementer_numero_porc()

       # if GPIO.input(24) == GPIO.HIGH:
        #    break
        if GPIO.input(27) == GPIO.HIGH:
            print("BP incrémentation manuelle appuyé")
            incrementer_numero_porc()
            time.sleep(0.3)
        
        if GPIO.input(22) == GPIO.HIGH:
            print("BP décrémentation manuelle appuyé")
            decrementer_numero_porc()
            time.sleep(0.3)
        
        # if GPIO.input(18) == GPIO.HIGH:
            # print("BP3 : arrêt demandé.")
            # strip.set_all_pixels(Color(0, 0, 0))  # Éteint toutes les LED
            # strip.show()
            # ##########################################
            # # Config pour les nouvelles LED
            # ##########################################
            # #os.system("sudo systemctl stop camera.service")
            # os.system("sudo reboot")
            # break



        if not image_overlay_active:
            num_porc = lire_numero()
            overlay = np.zeros((scaled_height, scaled_width, 4), dtype=np.uint8)
            cv2.putText(overlay, f"N_Porc : {num_porc}", (10, scaled_height - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255, 255), 2)
            overlay = cv2.rotate(overlay, cv2.ROTATE_90_COUNTERCLOCKWISE)

            cam.set_overlay(overlay)



except KeyboardInterrupt:
    pass
finally:
    cam.stop_preview()
    cam.stop()
    cam.close()
    #tcflush(stdin, TCIOFLUSH)
    try:
        tcflush(stdin, TCIOFLUSH)
    except Exception as e:
        print(f"[WARN] Impossible de vider le tampon stdin : {e}")

    executor.shutdown(wait=True)
    GPIO.cleanup()
    analysis_queue.put(None)
    analysis_thread.join()

