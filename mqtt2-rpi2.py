import paho.mqtt.client as mqtt
import json
import csv
import time
import os
import gpiod
import struct
import subprocess

# Configuraci�n del broker MQTT
BROKER_ADDRESS = "138.100.69.52"  # Reemplaza con la IP de tu broker
PORT = 1883  # Puerto por defecto de MQTT
TOPIC = "sensores/datos"  # Tema que el Arduino publica

# Configuraci�n del bot�n
BUTTON_GPIO = 17
CHIP = "/dev/gpiochip0"  # Ruta del chip GPIO en Raspberry Pi 5
chip = gpiod.Chip(CHIP)
line = chip.get_lines([BUTTON_GPIO])
line.request(consumer="button", type=gpiod.LINE_REQ_DIR_IN, default_vals=[0])

# Variables globales
recording = False
last_button_press = 0  # Para manejar el retardo del bot�n
collected_data = []

def on_message(client, userdata, message):
    global collected_data, recording
    try:
        data = json.loads(message.payload.decode('utf-8'))
        if recording:
            collected_data.append((data['C1'], data['C2'], data['C3'], data['C4']))
    except json.JSONDecodeError:
        print("[ERROR] No se pudo decodificar el mensaje JSON.")

def button_callback():
    global recording, last_button_press, collected_data
    current_time = time.time()
    if not recording and (current_time - last_button_press) >= 7:  # Retardo de 7 segundos
        print("[INFO] Iniciando grabaci�n de 5 segundos...")
        recording = True
        collected_data = []
        start_time = time.time()
        while time.time() - start_time < 5:
            client.loop()
        recording = False
        print("[INFO] Finalizando grabaci�n y guardando datos...")
        save_binary_data()
        last_button_press = current_time

def save_binary_data():
    if collected_data:
        directory = os.path.abspath("RAW")  # Asegurar ruta absoluta
        if not os.path.exists(directory):
            os.makedirs(directory)
        bin_filename = os.path.join(directory, f"data_{int(time.time())}.bin")
        try:
            with open(bin_filename, "wb") as file:
                for entry in collected_data:
                    file.write(struct.pack("4i", *entry))  # Guardar como enteros en binario
            print(f"[INFO] Datos guardados en formato binario en {bin_filename}")
            csv_filename = convert_to_csv(bin_filename)
            if csv_filename:
                ejecutar_script_resistencias(csv_filename)
        except Exception as e:
            print(f"[ERROR] No se pudo guardar el archivo binario: {e}")
    else:
        print("[WARNING] No se recopilaron datos durante la grabaci�n, no se gener� archivo.")

def convert_to_csv(bin_filename):
    csv_filename = bin_filename.replace(".bin", ".csv")
    try:
        with open(bin_filename, "rb") as bin_file, open(csv_filename, "w", newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["C1", "C2", "C3", "C4"])
            while True:
                data = bin_file.read(16)  # Leer 4 enteros (4 bytes cada uno)
                if not data:
                    break
                writer.writerow(struct.unpack("4i", data))
        print(f"[INFO] Datos convertidos a CSV en {csv_filename}")
        return csv_filename
    except Exception as e:
        print(f"[ERROR] No se pudo convertir a CSV: {e}")
        return None

def ejecutar_script_resistencias(csv_filename):
    script_resistencias = "resistencias.py"  # Nombre del script de resistencias
    try:
        subprocess.run(["python3", script_resistencias], check=True)
        print(f"[INFO] Script de c�lculo de resistencias ejecutado con �xito.")
    except Exception as e:
        print(f"[ERROR] No se pudo ejecutar el script de resistencias: {e}")

# Configuraci�n del cliente MQTT
client = mqtt.Client()
client.on_message = on_message
client.connect(BROKER_ADDRESS, PORT)
client.subscribe(TOPIC)

print(f"Escuchando mensajes en el tema '{TOPIC}'...")

# Mantener el cliente en ejecuci�n y monitorear el bot�n
try:
    while True:
        if line.get_values()[0] == 1:
            button_callback()
        client.loop()
except KeyboardInterrupt:
    print("[INFO] Saliendo del programa.")