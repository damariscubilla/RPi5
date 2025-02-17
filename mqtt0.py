import paho.mqtt.client as mqtt
import pandas as pd
import time
import csv
import os
from gpiozero import Button

# Configuraci�n
BROKER = "138.100.69.38"  # IP de la Raspberry Pi
TOPIC = "sensores/datos"
SAVE_DIR = "/home/caminos/ADS"  # Carpeta donde se guardar�n los archivos CSV
BUTTON_GPIO = 17  # GPIO del bot�n

# Variables de estado
RECORDING = False
data_buffer = []
button = Button(BUTTON_GPIO)

# Asegurar que la carpeta de almacenamiento exista
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)
    print(f"[INFO] Carpeta {SAVE_DIR} creada o ya existe.")

# Funci�n para alternar la grabaci�n al presionar el bot�n
def toggle_recording():
    global RECORDING
    RECORDING = not RECORDING
    if RECORDING:
        print("[INFO] Grabaci�n ACTIVADA.")
    else:
        print("[INFO] Grabaci�n DETENIDA.")

# Configurar el bot�n para alternar la grabaci�n
button.when_pressed = toggle_recording

# Funci�n que se ejecuta cuando el cliente MQTT se conecta al broker
def on_connect(client, userdata, flags, rc):
    print(f"[INFO] Conectado al broker MQTT con c�digo: {rc}")
    client.subscribe(TOPIC)

# Funci�n que se ejecuta cuando se recibe un mensaje MQTT
def on_message(client, userdata, msg):
    global data_buffer, RECORDING

    message = msg.payload.decode()
    print(f"[INFO] Mensaje recibido: {message}")  # Depuraci�n

    if RECORDING:
        try:
            data = eval(message)  # Convierte el JSON a diccionario
            data_buffer.append(data)
            print(f"[INFO] Datos guardados en buffer: {len(data_buffer)} registros")
        except Exception as e:
            print(f"[ERROR] No se pudo procesar el mensaje: {e}")

# Configurar el cliente MQTT
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, 1883, 60)
client.loop_start()

# Bucle principal: Guardar datos cada 5 segundos si la grabaci�n est� activa
while True:
    if RECORDING and len(data_buffer) > 0:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(SAVE_DIR, f"datos_{timestamp}.csv")

        print(f"[INFO] Intentando guardar archivo en: {filename}")

        try:
            df = pd.DataFrame(data_buffer)
            df.to_csv(filename, index=False)
            print(f"[INFO] Archivo {filename} guardado con {len(data_buffer)} registros.")
        except Exception as e:
            print(f"[ERROR] No se pudo guardar el archivo: {e}")

        data_buffer = []  # Vaciar el buffer para el siguiente ciclo

    time.sleep(5)  # Espera 5 segundos antes de la siguiente escritura
