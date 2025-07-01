#!/usr/bin/env python3
import os
import time
import json
import csv
import threading
import subprocess
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, TextBox
import paho.mqtt.client as mqtt
from datetime import datetime

# --------------------------------------------------------------------
# Parámetros de conversión ADC
# --------------------------------------------------------------------
Vref = 4.096           # Voltaje de referencia del ADC
ADC_MAX = 32768         # Valor máximo del ADC

def raw_to_voltage(raw):
    """
    Convierte un valor raw del ADC a voltaje.
    """
    return (raw / ADC_MAX) * Vref

# --------------------------------------------------------------------
# Variables globales
# --------------------------------------------------------------------
live_data = []         # Lista de datos para la gráfica (timestamp, C1, C2, C3, C4)
marker_events = []     # Lista de eventos de fotointerruptores (timestamp, sensor, estado)
recorded_data = []     # Lista de datos completos grabados (timestamp, C1, C2, C3, C4, F1, F2, F3)
recording = False      # Indicador de grabación activa
graph_window = 10      # Ventana de tiempo para la gráfica (en segundos)

# --------------------------------------------------------------------
# Configuración y callbacks del MQTT
# --------------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    """
    Callback que se ejecuta al conectar con el broker MQTT.
    Se suscribe al tópico 'sensores/datos'.
    """
    print("Conectado a MQTT, código:", rc)
    client.subscribe("sensores/datos")

def on_message(client, userdata, msg):
    """
    Callback que se ejecuta al recibir un mensaje MQTT.
    Procesa el mensaje y actualiza las listas globales con los datos recibidos.
    """
    global live_data, marker_events, recorded_data, recording, graph_window
    try:
        data = json.loads(msg.payload.decode('utf-8'))
    except Exception as e:
        print("[ERROR] JSON:", e)
        return

    # Obtener el timestamp enviado (en milisegundos) y convertirlo a segundos
    ts = data.get("timestamp", time.time() * 1000)
    t_unix = ts / 1000.0

    # Almacenar los datos de canales C para la gráfica
    entry = (t_unix, data['C1'], data['C2'], data['C3'], data['C4'])
    live_data.append(entry)

    # Almacenar eventos de fotointerruptores (F1, F2, F3)
    for i in range(1, 4):
        if data.get(f"F{i}", False):
            marker_events.append((t_unix, i, "ON"))

    # Filtrar datos antiguos en función del último timestamp recibido y la ventana
    if live_data:
        latest_timestamp = live_data[-1][0]
    else:
        latest_timestamp = 0
    cutoff = latest_timestamp - graph_window
    live_data[:] = [d for d in live_data if d[0] >= cutoff]
    marker_events[:] = [m for m in marker_events if m[0] >= cutoff]

    # Si se está grabando, guardar los datos completos en recorded_data
    if recording:
        recorded_data.append((
            t_unix,
            data['C1'],
            data['C2'],
            data['C3'],
            data['C4'],
            int(data.get("F1", False)),
            int(data.get("F2", False)),
            int(data.get("F3", False))
        ))

# Configurar el cliente MQTT
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("138.100.69.52", 1883, 60)
client.loop_start()

# --------------------------------------------------------------------
# Funciones para grabar y guardar datos
# --------------------------------------------------------------------
def save_csv_data():
    """
    Guarda los datos grabados en un archivo CSV.
    El nombre del archivo tendrá el formato:
      YYYYMMDD-DatosRaw-EnsayoX.csv
    donde YYYYMMDD es la fecha actual y X es el número de ensayo incremental.
    """
    if recorded_data:
        # Obtener la fecha actual en formato YYYYMMDD
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")

        # Definir el directorio base donde se guardarán los archivos (por ejemplo, carpeta "CSV")
        base_directory = os.path.abspath("CSV")
        os.makedirs(base_directory, exist_ok=True)

        # Contar los archivos existentes para el día actual
        existing_files = [f for f in os.listdir(base_directory)
                          if f.startswith(f"{date_str}-DatosRaw-Ensayo") and f.endswith(".csv")]
        ensayo_number = len(existing_files) + 1

        # Crear el nombre de archivo con el formato deseado
        filename = os.path.join(base_directory, f"{date_str}-DatosRaw-Ensayo{ensayo_number}.csv")

        # Guardar los datos en el archivo CSV
        with open(filename, "w", newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "C1", "C2", "C3", "C4", "F1", "F2", "F3"])
            for entry in recorded_data:
                writer.writerow(entry)
        print(f"[INFO] CSV guardado en {filename}")
        ejecutar_script_resistencias(filename)
        status_text.set_text("Grabación finalizada")
    else:
        print("[WARNING] No se grabaron datos.")

def ejecutar_script_resistencias(csv_filename):
    """
    Ejecuta el script de procesamiento de resistencias, pasando como argumento
    el nombre del archivo CSV recién guardado.
    """
    script_resistencias = "resistencias2.py"
    try:
        subprocess.run(["python3", script_resistencias, csv_filename], check=True)
        print("[INFO] Script resistencias ejecutado.")
    except Exception as e:
        print(f"[ERROR] Script resistencias: {e}")

def start_recording(duration):
    """
    Inicia la grabación de datos durante un periodo determinado (en segundos).
    """
    global recording, recorded_data
    if not recording:
        print(f"[INFO] Grabando {duration} s...")
        recording = True
        recorded_data = []  # Reinicia los datos grabados
        status_text.set_text("Grabando...")
        threading.Timer(duration, stop_recording).start()

def stop_recording():
    """
    Detiene la grabación de datos y guarda el archivo CSV.
    """
    global recording
    recording = False
    print("[INFO] Grabación finalizada. Guardando...")
    save_csv_data()

# --------------------------------------------------------------------
# Configuración del gráfico en tiempo real
# --------------------------------------------------------------------
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.35, right=0.8)
ax.set_xlabel("Tiempo (s)")
ax.set_ylabel("Resistencia (Ω)")
ax.set_title("Resistencias en tiempo real")
ax.set_xlim(0, graph_window)

# Líneas para graficar las resistencias (calculadas a partir de C1, C2, C3 y C4)
line_r1, = ax.plot([], [], label="R1 (C2-C1)", color='blue')
line_r2, = ax.plot([], [], label="R2 (C3-C2)", color='green')
line_r3, = ax.plot([], [], label="R3 (C4-C3)", color='orange')
ax.legend(loc='upper left', bbox_to_anchor=(1, 1))

# Texto de estado en la parte superior del gráfico
status_text = fig.text(0.5, 0.98, "Estado: Sin grabación", ha='center', va='center', fontsize=12)

vertical_lines = []  # Lista para almacenar las líneas verticales que indican eventos

def update_plot(frame):
    """
    Función que se ejecuta periódicamente para actualizar el gráfico en tiempo real.
    Calcula las resistencias a partir de los datos y dibuja líneas verticales para cada evento.
    """
    global vertical_lines
    # Usar el último timestamp de live_data como referencia para la ventana de tiempo
    if live_data:
        current_timestamp = live_data[-1][0]
    else:
        current_timestamp = 0
    t0 = current_timestamp - graph_window

    times = []
    r1_list = []
    r2_list = []
    r3_list = []
    # Calcular tiempo relativo y resistencias para cada dato
    for entry in live_data:
        ts, c1, c2, c3, c4 = entry
        t_rel = ts - t0
        v1 = raw_to_voltage(c1)
        v2 = raw_to_voltage(c2)
        v3 = raw_to_voltage(c3)
        v4 = raw_to_voltage(c4)
        I = v1 / 10.0 if abs(v1) > 1e-6 else 1e-6
        r1_val = (v2-v1) / I
        r2_val = (v3-v2) / I
        r3_val = (v4-v3) / I
        times.append(t_rel)
        r1_list.append(r1_val)
        r2_list.append(r2_val)
        r3_list.append(r3_val)

    # Actualizar las líneas del gráfico
    line_r1.set_data(times, r1_list)
    line_r2.set_data(times, r2_list)
    line_r3.set_data(times, r3_list)
    ax.set_xlim(0, graph_window)
    ax.relim()
    ax.autoscale_view(scalex=False)

    # Eliminar las líneas verticales anteriores
    for vl in vertical_lines:
        vl.remove()
    vertical_lines = []

    # Obtener los colores de las líneas de resistencias
    r1_color = line_r1.get_color()  # Azul para R1
    r2_color = line_r2.get_color()  # Verde para R2
    r3_color = line_r3.get_color()  # Naranja para R3

    # Dibujar una línea vertical para cada evento (F1, F2, F3) con el color correspondiente
    for evt in marker_events:
        evt_time, sensor, state = evt
        if evt_time >= t0:
            x_evt = evt_time - t0
            # Asignar el color según el sensor
            if sensor == 1:
                color = r1_color  # Mismo color que R1 para F1 (azul)
            elif sensor == 2:
                color = r2_color  # Mismo color que R2 para F2 (verde)
            elif sensor == 3:
                color = r3_color  # Mismo color que R3 para F3 (naranja)
            else:
                color = 'red'  # Color por defecto en caso de error
            vl = ax.axvline(x=x_evt, color=color, linestyle='--', linewidth=1)
            vertical_lines.append(vl)

    return [line_r1, line_r2, line_r3] + vertical_lines

ani = FuncAnimation(fig, update_plot, interval=100)

# --------------------------------------------------------------------
# Widgets para la interfaz (Grabación y ventana del gráfico)
# --------------------------------------------------------------------
ax_box_record = plt.axes([0.15, 0.20, 0.25, 0.075])
text_box_record = TextBox(ax_box_record, 'Duración (s): ', initial="5")

def record_button_callback(event):
    """
    Callback del botón 'Grabar'. Inicia la grabación según la duración indicada.
    """
    try:
        duration = float(text_box_record.text)
        start_recording(duration)
    except ValueError:
        print("[ERROR] Valor no válido.")

ax_button_record = plt.axes([0.45, 0.20, 0.15, 0.075])
record_button = Button(ax_button_record, 'Grabar')
record_button.on_clicked(record_button_callback)

ax_box_window = plt.axes([0.15, 0.10, 0.25, 0.075])
text_box_window = TextBox(ax_box_window, 'Ventana (s): ', initial=str(graph_window))

def window_box_callback(text):
    """
    Callback para actualizar la ventana de tiempo del gráfico.
    """
    global graph_window
    try:
        new_window = float(text)
        if new_window > 0:
            graph_window = new_window
            print("[INFO] Ventana actualizada a", graph_window)
        else:
            print("[ERROR] Valor debe ser > 0")
    except ValueError:
        print("[ERROR] Valor inválido")

text_box_window.on_submit(window_box_callback)

# Mostrar el gráfico y entrar en el loop de la interfaz
plt.show()

client.loop_stop()
client.disconnect()
