import serial
import struct

import threading
import time
from datetime import datetime
import random
import os
import csv
import serial.tools.list_ports
import math

import dearpygui.dearpygui as dpg
import pyautogui

screen_width, screen_height = pyautogui.size()
screen_height *= 0.9

# Proprietà del pacchetto: [ID, dimensione in byte].
# La dimensione deve essere quella del pacchetto con ID compreso (ovvero così come arriva dalla ground station).

ID = 0
size = 1
gps_loc_pkt = [1, 28]
gps_clk_pkt = [2, 28]
power_pkt = [3, 12]
imu_pkt = [4, 32]

# Dati ricevuti via radio

data = [0] * 24
data_label = [""] * 24
(
    clock,
    nSat,
    lat,
    lon,
    alt,
    speed,
    cog,
    day,
    month,
    year,
    hour,
    minute,
    second,
    voltage,
    current,
    power,
    accX,
    accY,
    accZ,
    roll,
    pitch,
    yaw,
    temp,
) = range(23)
data_dec = [0, 0, 6, 6, 2, 2, 0, 0, 0, 0, 0, 0, 0, 4, 4, 4, 3, 3, 3, 0, 0, 0, 1]

adc_smoothing_factor = 0.05
adc_cal_voltage = [
    10.957538394,
    1.517369447,
]  # Costanti m e q della funzione y = mx + q, dove data in input x la tensione letta dall'ADC, y è la tensione reale al partitore
adc_cal_current = [
    20.13434425,
    2.687814483,
]  # Costanti m e q della funzione y = mx + q, dove data in input x la tensione letta dall'ADC, y è la corrente reale al partitore
current_threshold_filter = 4  # Corrente sotto la quale il dato di corrente viene considerato nullo, serve ad evitare le elevate imprecisioni del sensore/partitore per bassi amperaggi

data_label[clock] = "Tempo"
data_label[nSat] = "Satelliti"
data_label[lat] = "Latitudine"
data_label[lon] = "Longitudine"
data_label[alt] = "Altitudine [m]"
data_label[speed] = "Velocità [km/h]"
data_label[cog] = "COG"
data_label[day] = "Giorno"
data_label[month] = "Mese"
data_label[year] = "Anno"
data_label[hour] = "Ora"
data_label[minute] = "Minuto"
data_label[second] = "Secondo"
data_label[voltage] = "Tensione [V]"
data_label[current] = "Corrente [A]"
data_label[power] = "Potenza el. [W]"
data_label[accX] = "Accelerazione X"
data_label[accY] = "Accelerazione Y"
data_label[accZ] = "Accelerazione Z"
data_label[roll] = "Roll [°]"
data_label[pitch] = "Pitch [°]"
data_label[yaw] = "Yaw [°]"
data_label[temp] = "Temperatura [°C]"

# Dati da mostrare in tabella

table_data = [
    clock,
    nSat,
    lat,
    lon,
    alt,
    speed,
    cog,
    voltage,
    current,
    power,
    accX,
    accY,
    accZ,
    roll,
    pitch,
    yaw,
    temp,
]

# Dati dei plot

marker_colors = [
    [102, 187, 106, 255],  # Verde
    [66, 165, 245, 255],  # Blu
    [239, 83, 80, 255],  # Rosso
    [255, 202, 40, 255],  # Giallo
    [171, 71, 188, 255],  # Viola
]


# Frequenza di scrittura dei log.

logging = False
log_marker = "-"
log_last_update = time.time()
log_update_frequency = 10

# Orizzonte artificiale

horizon_last_update = time.time()
horizon_update_frequency = 5

# Oggetto plot, definito in base a un ID progressivo, che corrisponde anche all'indice con il quale lo stesso plot è salvato nella lista plots.

plots = []
plot_types = [
    "Posizione",
    "Potenza",
    "Assetto",
    "Accelerazione",
    "Traiettoria",
]  # Mantenere ultima "Traiettoria" o modificare combo-item di selezione plot.


class PlotData:

    def __init__(self, ID, plot_type):
        self.ID = ID
        self.plot_type = plot_type
        self.name = plot_types[plot_type]
        self.pos = [screen_width / 4, self.ID * screen_height / 2]
        self.height = screen_height / 2
        self.width = screen_width * 0.75

        match plot_type:

            case 0:
                self.data_x = []
                self.data_y = [[], []]
                self.data_x_ID = clock
                self.data_y_ID = [alt, speed]

            case 1:
                self.data_x = []
                self.data_y = [[], [], []]
                self.data_x_ID = clock
                self.data_y_ID = [voltage, current, power]

            case 2:
                self.data_x = []
                self.data_y = [[], [], []]
                self.data_x_ID = clock
                self.data_y_ID = [roll, pitch, yaw]

            case 3:
                self.data_x = []
                self.data_y = [[], [], []]
                self.data_x_ID = clock
                self.data_y_ID = [accX, accY, accZ]

            case 4:
                self.data_x = []
                self.data_y = [[]]
                self.data_x_ID = lon
                self.data_y_ID = [lat]
                self.height = screen_height / 2
                self.width = screen_width / 2
                self.start_point = [data[lat], data[lon]]
                self.dist_x = []
                self.dist_y = [[]]

    def update_data(self):
        self.data_x.append(data[self.data_x_ID])
        if self.plot_type == plot_types.index("Traiettoria"):
            self.dist_x.append(
                (self.start_point[1] - data[lon])
                * 111320
                * math.cos(math.radians(self.start_point[0]))
            )

        for i, data_id in enumerate(self.data_y_ID):
            self.data_y[i].append(data[data_id])

            if self.plot_type == plot_types.index("Traiettoria"):
                self.dist_y[i].append((self.start_point[0] - data[lat]) * 111320)

    def get_x_label(self):
        return data_label[self.data_x_ID]

    def get_y_axis_limits(self, buffer):

        if not buffer == None:
            __max_value = max(
                value for sublist in self.data_y[-buffer:] for value in sublist
            )
            __min_value = min(
                value for sublist in self.data_y[-buffer:] for value in sublist
            )
        else:
            __max_value = max(value for sublist in self.data_y for value in sublist)
            __min_value = min(value for sublist in self.data_y for value in sublist)

        __delta = __max_value - __min_value
        return [__min_value - abs(0.1 * __delta), __max_value + abs(0.1 * __delta)]

    def get_data_x(self, buffer):

        if buffer == None:
            if not self.plot_type == plot_types.index("Traiettoria"):
                return self.data_x
            else:
                return self.dist_x
        else:
            if not self.plot_type == plot_types.index("Traiettoria"):
                return self.data_x[-buffer:]
            else:
                return self.dist_x[-buffer:]

    def get_data_y(self, buffer):

        if buffer == None:
            if not self.plot_type == plot_types.index("Traiettoria"):
                return self.data_y
            else:
                return self.dist_y

        else:
            if not self.plot_type == plot_types.index("Traiettoria"):
                return [serie[-buffer:] for serie in self.data_y]
            else:
                return [serie[-buffer:] for serie in self.dist_y]


# Viene creata la viewport (coincide con la finestra di Windows).

dpg.create_context()
dpg.create_viewport(title="LIFTUP Data Monitor", width=600, height=600)

# Apre la porta seriale "COM-X" passata come argomento stringa


def open_serial(port):
    global ser

    try:
        ser = serial.Serial(port, 500000)
        dpg.set_value("PORT-C", ser.port)
    except:
        pass


# Usare o specificando una porta specifica da aprire con argomenti (porta); oppure in modalità automatica (cerca nella descrione-porta ricevuta da OS le keyword con arg (None)


def port_select(port_selected):
    global ports
    ports = sorted(serial.tools.list_ports.comports())
    port_description_keywords = ["UART", "CP210x", "CH340"]

    if port_selected == None:
        for port in ports:
            for keyword in port_description_keywords:
                if keyword in port[1]:
                    open_serial(port[0])

    else:
        open_serial(port_selected)

    dpg.configure_item("PORT-C", items=[port[0] for port in ports])


# Restituisce il valore ottenuto dalla relazione lineare di calibrazione specificata


def adc_linear_correction(reading, regr):
    return reading * regr[0] + regr[1]


# I pacchetti sono decoificati. I byte sono interpretati dalla variabile ID (già decodificata) in poi. Per questo alla dimensione del pacchetto
# originale si sottrae 4 (4 byte dell'integer ID).


def decode_packet(packet_ID):

    if packet_ID == gps_loc_pkt[ID]:

        packet_data = ser.read(gps_loc_pkt[size] - 4)
        s = struct.unpack("<Ifffff", packet_data)
        data[nSat], data[lat], data[lon], data[alt], data[speed], data[cog] = s

    if packet_ID == gps_clk_pkt[ID]:

        packet_data = ser.read(gps_clk_pkt[size] - 4)
        s = struct.unpack("<IIIIII", packet_data)
        data[day], data[month], data[year], data[hour], data[minute], data[second] = s

    if packet_ID == power_pkt[ID]:

        packet_data = ser.read(power_pkt[size] - 4)
        s = struct.unpack("<ff", packet_data)
        data[voltage] = (
            data[voltage] * (1 - adc_smoothing_factor)
            + adc_linear_correction(s[0], adc_cal_voltage) * adc_smoothing_factor
        )

        if adc_linear_correction(s[1], adc_cal_current) > current_threshold_filter:
            data[current] = (
                data[current] * (1 - adc_smoothing_factor)
                + adc_linear_correction(s[1], adc_cal_current) * adc_smoothing_factor
            )
        else:
            data[current] = data[current] * (1 - adc_smoothing_factor)

        data[power] = data[voltage] * data[current]

    if packet_ID == imu_pkt[ID]:

        packet_data = ser.read(imu_pkt[size] - 4)
        s = struct.unpack("<fffffff", packet_data)
        (
            data[accX],
            data[accY],
            data[accZ],
            data[roll],
            data[pitch],
            data[yaw],
            data[temp],
        ) = s


# Stabilisce l'ID del pacchetto ricevuto e lo passa come argomento alla funzione di decodifica.


def update_data():

    while True:

        data[clock] = time.time()

        try:
            # Legge l'ID del pacchetto, ovvero i primi 4 byte
            packet_ID_bytes = ser.read(4)
            packet_ID = struct.unpack("<I", packet_ID_bytes)[
                0
            ]  # Interpreta i 4 byte come un intero

            # Decodifica il pacchetto
            decode_packet(packet_ID)
        except:
            pass


# Simula la ricezione dei dati - per motivi di sviluppo


def simulate_update_data():
    global data

    data[lat] = 45
    data[lon] = 11

    # Parametri per la variazione continua
    variation_factors = {
        "nSat": (0, 30),
        "lat": (-0.001, 0.001),
        "lon": (-0.001, 0.001),
        "alt": (-10, 10),
        "speed": (-5, 5),
        "cog": (-5, 5),
        "day": (0, 1),
        "month": (0, 1),
        "year": (0, 1),
        "hour": (0, 1),
        "minute": (0, 1),
        "second": (0, 1),
        "voltage": (-0.1, 0.1),
        "current": (-0.5, 0.5),
    }

    def apply_variation(value, variation_range):
        return value + random.uniform(*variation_range)

    while True:

        data[clock] = time.time()

        # Genera dati casuali plausibili per GPS con variazione continua
        data[nSat] = apply_variation(data[nSat], variation_factors["nSat"])

        R = 6371.0
        angle = 2 * math.pi * (data[clock] % 10) / 10
        lat_offset = 3 / R * math.cos(angle)
        data[lat] = 45 + math.degrees(lat_offset)

        lat_rad = math.radians(45)
        angle = 2 * math.pi * (data[clock] % 10) / 10
        lon_offset = 3 / (R * math.cos(lat_rad)) * math.sin(angle)
        data[lon] = 12 + math.degrees(lon_offset)

        data[alt] = apply_variation(data[alt], variation_factors["alt"])
        data[speed] = apply_variation(data[speed], variation_factors["speed"])
        data[cog] = apply_variation(data[cog], variation_factors["cog"])

        # Mantieni i valori di nSat entro i limiti validi
        data[nSat] = max(0, min(30, data[nSat]))

        # Genera dati casuali plausibili per l'orologio GPS con variazione continua
        data[day] = int(apply_variation(data[day], variation_factors["day"]))
        data[month] = int(apply_variation(data[month], variation_factors["month"]))
        data[year] = int(apply_variation(data[year], variation_factors["year"]))
        data[hour] = int(apply_variation(data[hour], variation_factors["hour"]))
        data[minute] = int(apply_variation(data[minute], variation_factors["minute"]))
        data[second] = int(apply_variation(data[second], variation_factors["second"]))

        # Assicurati che i valori temporali siano validi
        data[day] = max(1, min(31, data[day]))
        data[month] = max(1, min(12, data[month]))
        data[hour] = max(0, min(23, data[hour]))
        data[minute] = max(0, min(59, data[minute]))
        data[second] = max(0, min(59, data[second]))

        # Genera dati casuali plausibili per il pacchetto di potenza con variazione continua
        voltage_value = apply_variation(
            data[voltage], variation_factors["voltage"]
        )  # Voltaggio in Volt
        current_value = apply_variation(
            data[current], variation_factors["current"]
        )  # Corrente in Ampere

        # Applica la formula di smoothing e correzione
        data[voltage] = (
            data[voltage] * (1 - adc_smoothing_factor)
            + voltage_value * adc_smoothing_factor
        )
        data[current] = (
            data[current] * (1 - adc_smoothing_factor)
            + current_value * adc_smoothing_factor
        )
        data[power] = data[voltage] * data[current]

        time.sleep(0.05)


# Definiti font e temi

with dpg.font_registry():
    font1 = dpg.add_font("brass-mono-bold.ttf", 18)

with dpg.theme(tag="PL-T"):
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_style(
            dpg.mvPlotStyleVar_LineWeight, 3, category=dpg.mvThemeCat_Plots
        )

with dpg.theme(tag="LOG-B-theme"):
    with dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (239, 83, 80, 150))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (239, 83, 80, 200))

with dpg.theme(tag="LOG-B-REC-theme"):
    with dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (239, 83, 80, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (239, 83, 80, 150))

# Callback dei pulsanti dei controlli di log.


def log_button_callback():
    global logging

    if logging:
        dpg.set_value("LOG-N", "Filename...")
        logging = False
        dpg.configure_item("LOG-B", label="START LOG")
    else:
        dpg.set_value("LOG-N", datetime.now().strftime("Log-%d.%m.%Y-%H.%M.%S.csv"))
        logging = True
        dpg.configure_item("LOG-B", label="STOP LOG")
        dpg.bind_item_theme("LOG-B", "LOG-B-REC-theme")


# Callback degli elementi grafici per la selezione della porta.


def port_callback():
    try:
        ser.close()
    except:
        pass
    port_select(dpg.get_value("PORT-C"))


def port_button_callback():
    ports = sorted(serial.tools.list_ports.comports())
    dpg.configure_item("PORT-C", items=[port[0] for port in ports])


# Creazione e configurazione finestra dei dati in diretta. Non richiede siano già stati ricevuti i dati da inserire.


def data_table_create():

    with dpg.window(label="Tabella dati", height=screen_height, width=screen_width / 4):

        left_item_width = screen_width / 4 * 0.705
        rigth_item_width = screen_width / 4 * 0.225

        # Selezione porta

        with dpg.group(horizontal=True):
            dpg.add_combo(
                width=left_item_width,
                height_mode=dpg.mvComboHeight_Small,
                tag="PORT-C",
                callback=port_callback,
            )
            dpg.add_button(
                tag="PORT-B",
                label="AGGIORNA",
                width=rigth_item_width,
                callback=port_button_callback,
            )

        # Controlli dei log

        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag="LOG-N", default_value="Filename...", width=left_item_width
            )
            dpg.add_button(
                tag="LOG-B",
                label="START LOG",
                width=rigth_item_width,
                callback=log_button_callback,
            )
            dpg.bind_item_theme("LOG-B", "LOG-B-theme")

        # Tabella dei dati

        with dpg.table(
            header_row=False,
            row_background=True,
            borders_innerH=True,
            borders_outerH=True,
            borders_innerV=True,
            borders_outerV=True,
        ):

            dpg.add_table_column()
            dpg.add_table_column()

            for i in table_data:
                with dpg.table_row():
                    dpg.add_text(data_label[i])
                    data_text = dpg.add_text("-", tag=f"DT{i}")
                    dpg.bind_item_font(data_text, font1)


# Funzione di callback chiamata a selezione avvenuta del dato da diagrammare. Gli argomenti sono: sender (contiene il tag dell'elemento che ha chiamato la callback, gestito automaticamente dall'API), app_data (contiene la stringa selezionata, gestito automaticamente dall'API) e user_data (argomento specificato alla chiamata che contiene l'ID del plot da cui arriva la callback).
# Azzera gli assi del plot relativo. Non richiede siano già stati ricevuti dati.


def plot_selection_callback(sender, app_data, user_data):

    plot = plots[user_data]

    if sender == f"PL{plot.ID}-C":

        for data_ID in plot.data_y_ID:
            dpg.delete_item(f"PL{plot.ID}-YA-{data_ID}")

        plots[plot.ID] = PlotData(plot.ID, plot_types.index(app_data))
        plot = plots[plot.ID]

        for i, data_ID in enumerate(plot.data_y_ID):
            dpg.add_line_series(
                plot.get_data_x(None),
                plot.get_data_y(None)[i],
                label=data_label[data_ID],
                parent=f"PL{plot.ID}-YA",
                tag=f"PL{plot.ID}-YA-{data_ID}",
            )
            dpg.bind_item_theme(f"PL{plot.ID}-YA-{data_ID}", "PL-T")


# Funzione di callback dei bottoni di controllo dei plot.


def plot_button_callback(sender, app_data, user_data):
    global marker_i, log_marker

    plot = plots[user_data]

    # Tasto di sync (pareggia la dimensione del buffer in tutti i plot).

    if sender == f"PL{plot.ID}-S":
        for p in plots:
            if not p.ID == plot:
                dpg.set_value(f"PL{p.ID}-B", dpg.get_value(f"PL{plot.ID}-B"))

    # Tasto di aggiunta dei marker.

    if sender.startswith("PL") and sender.endswith("-M"):

        marker_i += 1
        marker_color = marker_colors[random.randint(0, len(marker_colors) - 1)]
        log_marker = f"M{marker_i}"

        for p in plots:
            for serie in p.get_data_y(None):
                dpg.add_plot_annotation(
                    parent=f"PL{p.ID}",
                    label=f"M{marker_i}",
                    default_value=(p.get_data_x(None)[-1], serie[-1]),
                    color=marker_color,
                )

    if sender == f"PL{plot.ID}-D":
        plots[user_data] = PlotData(plot.ID, plot.plot_type)


# Creazione del plot, con argomento l'ID del plot da creare. Ogni volta che la funzione è chiamata viene generato il plot relativo al dato ID.
# Generare i plot con ID progressivo !!!


def plot_create(plot_type):

    plot = PlotData(len(plots), plot_type)
    plots.append(plot)

    with dpg.window(
        label=f"Diagramma in tempo reale #{plot.ID}",
        pos=plot.pos,
        height=plot.height,
        width=plot.width,
    ):

        with dpg.group(horizontal=True):
            if not plot.plot_type == plot_types.index("Traiettoria"):
                dpg.add_combo(
                    plot_types[:-1],
                    width=200,
                    height_mode=dpg.mvComboHeight_Small,
                    tag=f"PL{plot.ID}-C",
                    default_value=plot.name,
                    callback=plot_selection_callback,
                    user_data=plot.ID,
                )
            dpg.add_radio_button(
                items=("Manuale", "Completo", "Insegui"),
                horizontal=True,
                default_value="Completo",
                tag=f"PL{plot.ID}-RB",
            )
            dpg.add_slider_int(
                label="Buffer",
                tag=f"PL{plot.ID}-B",
                default_value=1000,
                min_value=100,
                max_value=5000,
                width=200,
            )
            dpg.add_button(
                tag=f"PL{plot.ID}-S",
                label="Sync",
                callback=plot_button_callback,
                user_data=plot.ID,
            )
            dpg.add_button(
                tag=f"PL{plot.ID}-M",
                label="Marker",
                callback=plot_button_callback,
                user_data=plot.ID,
            )
            dpg.add_button(
                tag=f"PL{plot.ID}-D",
                label="Clear",
                callback=plot_button_callback,
                user_data=plot.ID,
            )
            global marker_i
            marker_i = 0

        with dpg.plot(
            tag=f"PL{plot.ID}", height=plot.height - 70, width=plot.width * 0.97
        ):

            dpg.add_plot_axis(
                dpg.mvXAxis,
                label=plot.get_x_label(),
                tag=f"PL{plot.ID}-XA",
                time=(plot.data_x_ID == clock),
            )
            dpg.add_plot_axis(dpg.mvYAxis, tag=f"PL{plot.ID}-YA")

            if not plot.plot_type == plot_types.index("Traiettoria"):
                dpg.add_plot_legend()
            else:
                dpg.configure_item(f"PL{plot.ID}-XA", label="Distanza Ovest-Est")
                dpg.configure_item(f"PL{plot.ID}-YA", label="Distanza Sud-Nord")

            for i, data_ID in enumerate(plot.data_y_ID):
                dpg.add_line_series(
                    plot.get_data_x(None),
                    plot.get_data_y(None)[i],
                    label=data_label[data_ID],
                    parent=f"PL{plot.ID}-YA",
                    tag=f"PL{plot.ID}-YA-{data_ID}",
                )
                dpg.bind_item_theme(f"PL{plot.ID}-YA-{data_ID}", "PL-T")


# Aggiorna l'orizzionte artificiale con i dati di roll e pitch

def horizon_update():
    global horizon_last_update, horizon_update_frequency

    if time.time() - horizon_last_update > (1 / horizon_update_frequency):
        dpg.delete_item(
            "band_layer", children_only=True
        )  # Cancella i disegni precedenti
        dpg.delete_item(
            "notch_layer", children_only=True
        )  # Cancella le tacche precedenti

        width = screen_width*0.235
        height = screen_height*0.35
        notch_number = 3
        notch_interval_deg = 10

        # Calcola il punto centrale della giunzione
        center_y = height / 2 + math.radians(data[pitch]) * height * 0.7

        # Calcola l'offset verticale dovuto al roll
        half_width = width / 2
        offset = math.tan(math.radians(data[roll])) * (width / 2)

        # Calcola i punti dei vertici delle bande in base al pitch e roll centrati
        horizon_left = (0, center_y - offset)
        horizon_right = (width, center_y + offset)

        # Disegna la banda azzurra (superiore)
        dpg.draw_polygon(
            points=[(0, 0), (width, 0), horizon_right, horizon_left],
            color=(2, 51, 153, 255),
            fill=(2, 51, 153, 255),
            parent="band_layer",
        )

        # Disegna la banda marrone (inferiore)
        dpg.draw_polygon(
            points=[horizon_left, horizon_right, (width, height), (0, height)],
            color=(103, 51, 1, 255),
            fill=(103, 51, 1, 255),
            parent="band_layer",
        )

        # Disegna le tacche orizzontali
        for notch_angle in range(
            -notch_number * notch_interval_deg,
            (+notch_number + 1) * notch_interval_deg,
            notch_interval_deg,
        ):

            y = height / 2 + math.radians(notch_angle - data[pitch]) * height * 0.7

            notch_length = 150  # Lunghezza delle tacche
            notch_start = (
                half_width - notch_length / 2,
                y,
            )  # Punto di inizio tacche
            notch_end = (half_width + notch_length / 2, y)  # Punto di fine tacche

            # Funzione per ruotare un punto attorno a un punto di origine
            def rotate_point(point, origin, angle):
                ox, oy = origin
                px, py = point
                qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
                qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
                return qx, qy

            # Ruota i punti delle tacche
            rotated_notch_start = rotate_point(
                notch_start, (half_width, height/2), math.radians(data[roll])
            )
            rotated_notch_end = rotate_point(
                notch_end, (half_width, height/2), math.radians(data[roll])
            )

            dpg.draw_line(
                rotated_notch_start,
                rotated_notch_end,
                color=(255, 255, 255, 255),
                thickness=1.5,
                parent="notch_layer",
            )

            # Posiziona il testo vicino alla tacca
            text_position = (
                rotated_notch_end[0] + 10,
                rotated_notch_end[1] - 5,
            )
            dpg.draw_text(
                text_position,
                f"{notch_angle:.0f}°",
                color=(255, 255, 255, 255),
                size=12,
                parent="notch_layer",
            )

        dpg.draw_line(
            [half_width - 75, height / 2],
            [half_width - 10, height / 2],
            color=(0, 0, 0, 255),
            thickness=4,
            parent="notch_layer",
        )

        dpg.draw_line(
            [half_width + 10, height / 2],
            [half_width + 75, height / 2],
            color=(0, 0, 0, 255),
            thickness=4,
            parent="notch_layer",
        )

        horizon_last_update = time.time()

# Crea l'orizzonte artificiale

def horizon_create():

    # Crea la finestra principale
    with dpg.window(label="Orizzonte artificiale", pos=[screen_width, screen_height/2], width=screen_width/4, height=screen_height/2):

        with dpg.drawlist(width=screen_width*0.235, height=screen_height*0.35, tag="canvas"):
            with dpg.draw_layer(tag="band_layer"):
                pass  # Layer per i disegni delle bande
            with dpg.draw_layer(tag="notch_layer"):
                pass  # Layer per le tacche orizzontali


# Funzione di log. Gestisce anche il lampeggio del pulsante di registrazione.

def log_data():
    global logging, log_last_update, log_marker

    header_row = data_label[:] + ["Marker"]
    data_row = (
        [datetime.fromtimestamp(data[clock]).strftime("%H:%M:%S.%f")[:-3]]
        + data[:]
        + [log_marker]
    )

    if not hasattr(log_data, "prev_time"):
        log_data.prev_time = time.time()
        log_data.blink_status = True

    if logging:

        folder = "logs/"
        filename = folder + dpg.get_value("LOG-N")

        if not os.path.exists(folder):
            os.makedirs(folder)

        if not os.path.exists(filename):
            with open(filename, mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(header_row)

        if time.time() - log_last_update > (1 / log_update_frequency):
            with open(filename, mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(data_row)
                if not log_marker == "-":
                    log_marker = "-"

            log_last_update = time.time()

        if time.time() - log_data.prev_time > 1:
            if log_data.blink_status:
                dpg.bind_item_theme("LOG-B", "LOG-B-theme")
            else:
                dpg.bind_item_theme("LOG-B", "LOG-B-REC-theme")

            log_data.blink_status = not log_data.blink_status
            log_data.prev_time = time.time()


if __name__ == "__main__":

    data_table_create()

    plot_create(0)
    plot_create(4)
    horizon_create()
    dpg.show_metrics()

    port_select(None)
    threading.Thread(target=update_data).start()
    # threading.Thread(target=simulate_update_data).start()

    dpg.setup_dearpygui()
    dpg.show_viewport()

    while dpg.is_dearpygui_running():

        # Aggiornamento dei dati in tabella.

        for i in table_data:
            if i == clock:
                dpg.set_value(
                    f"DT{i}",
                    datetime.fromtimestamp(data[clock]).strftime("%H:%M:%S.%f")[:-3],
                )
            else:
                dpg.set_value(f"DT{i}", f"{data[i]:.{data_dec[i]}f}")

        # Aggiornamento dei dati dei plot, in base alla modalità di visualizzazione scelta.

        for plot in plots:

            plot.update_data()
            buffer = dpg.get_value(f"PL{plot.ID}-B")

            if dpg.get_value(f"PL{plot.ID}-RB") == "Manuale":

                dpg.set_axis_limits_auto(f"PL{plot.ID}-YA")

                if plot.plot_type == plot_types.index("Traiettoria"):
                    dpg.configure_item(f"PL{plot.ID}", equal_aspects=True)

            if dpg.get_value(f"PL{plot.ID}-RB") == "Insegui":
                for i, data_ID in enumerate(plot.data_y_ID):
                    if len(plot.get_data_x(None)) > dpg.get_value(f"PL{plot.ID}-B"):
                        if dpg.does_item_exist(f"PL{plot.ID}-YA-{data_ID}"):
                            dpg.set_value(
                                f"PL{plot.ID}-YA-{data_ID}",
                                [plot.get_data_x(buffer), plot.get_data_y(buffer)[i]],
                            )
                    else:
                        if dpg.does_item_exist(f"PL{plot.ID}-YA-{data_ID}"):
                            dpg.set_value(
                                f"PL{plot.ID}-YA-{data_ID}",
                                [plot.get_data_x(None), plot.get_data_y(None)[i]],
                            )

                if plot.plot_type == plot_types.index("Traiettoria"):
                    dpg.configure_item(f"PL{plot.ID}", equal_aspects=True)
                    dpg.fit_axis_data(f"PL{plot.ID}-XA")
                    dpg.fit_axis_data(f"PL{plot.ID}-YA")
                else:
                    dpg.fit_axis_data(f"PL{plot.ID}-XA")
                    dpg.set_axis_limits(
                        f"PL{plot.ID}-YA",
                        plot.get_y_axis_limits(buffer)[0],
                        plot.get_y_axis_limits(buffer)[1],
                    )

            else:
                for i, data_ID in enumerate(plot.data_y_ID):
                    if dpg.does_item_exist(f"PL{plot.ID}-YA-{data_ID}"):
                        dpg.set_value(
                            f"PL{plot.ID}-YA-{data_ID}",
                            [plot.get_data_x(None), plot.get_data_y(None)[i]],
                        )

            if dpg.get_value(f"PL{plot.ID}-RB") == "Completo":

                if plot.plot_type == plot_types.index("Traiettoria"):
                    dpg.configure_item(f"PL{plot.ID}", equal_aspects=True)
                    dpg.fit_axis_data(f"PL{plot.ID}-XA")
                    dpg.fit_axis_data(f"PL{plot.ID}-YA")
                else:
                    dpg.fit_axis_data(f"PL{plot.ID}-XA")
                    dpg.set_axis_limits(
                        f"PL{plot.ID}-YA",
                        plot.get_y_axis_limits(None)[0],
                        plot.get_y_axis_limits(None)[1],
                    )

            log_data()

        horizon_update()

        dpg.render_dearpygui_frame()

    dpg.destroy_context()
