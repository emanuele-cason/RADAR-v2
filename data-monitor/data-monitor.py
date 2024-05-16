import serial
import struct

import threading
import time
from datetime import datetime
import random
import os
import csv
import serial.tools.list_ports

import dearpygui.dearpygui as dpg
import pyautogui

screen_width, screen_height = pyautogui.size()
screen_height *= 0.9

# Proprietà del pacchetto: [ID, dimensione in byte].
# La dimensione deve essere quella del pacchetto con ID compreso (ovvero così come arriva dalla ground station).

ID = 0
size = 1
gps_loc = [1, 28]
gps_clk = [2, 28]
power = [3, 12]

# Dati ricevuti via radio

data = [0]*14
data_label = [""]*14
nSat, lat, lon, alt, speed, cog, day, month, year, hour, minute, second, voltage, current = range(14)
data_dec = [0,6,6,2,2,0,0,0,0,0,0,0,4,4]
adc_smoothing_factor = 0.05
adc_cal_voltage=[10.957538394, 1.517369447] # Costanti m e q della funzione y = mx + q, dove data in input x la tensione letta dall'ADC, y è la tensione reale al partitore
adc_cal_current=[20.13434425, 2.687814483] # Costanti m e q della funzione y = mx + q, dove data in input x la tensione letta dall'ADC, y è la corrente reale al partitore
current_threshold_filter = 4 # Corrente sotto la quale il dato di corrente viene considerato nullo, serve ad evitare le elevate imprecisioni del sensore/partitore per bassi amperaggi

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

logging = False

# Dati dei plot
marker_colors = [
    [102,187,106, 255],    # Verde
    [66,165,245, 255],    # Blu
    [239,83,80, 255],    # Rosso
    [255,202,40, 255],  # Giallo
    [171,71,188, 255],  # Viola
]

# Liste di liste (popolate in seguito) contenenti i dati degli assi x, y e dell'ID che identifica il tipo di dato (lat, lon, ...) riferiti all'ID dell'elemento grafico plot specificato come indice.
# Ad esempio il plot#69, che rappresenta la valocità in funzione del tempo avrà come dati sugli assi le liste: plot_data_x[69], plot_data_y[69], e come indice rappresentativo del dato: plot_data_ID[69] = 4.

plot_data_x = []
plot_data_y = []
plot_data_ID = []

# Viene creata la viewport (coincide con la finestra di Windows).

dpg.create_context()
dpg.create_viewport(title='LIFTUP Data Monitor', width=600, height=600)

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
    return reading*regr[0] + regr[1]

# I pacchetti sono decoificati. I byte sono interpretati dalla variabile ID (già decodificata) in poi. Per questo alla dimensione del pacchetto
# originale si sottrae 4 (4 byte dell'integer ID).

def decode_packet(packet_ID):
    
    if packet_ID == gps_loc[ID]:

        packet_data = ser.read(gps_loc[size] - 4)
        s = struct.unpack('<Ifffff', packet_data)
        data[nSat], data[lat], data[lon], data[alt], data[speed], data[cog] = s
        
    if packet_ID == gps_clk[ID]:

        packet_data = ser.read(gps_clk[size] - 4)
        s = struct.unpack('<IIIIII', packet_data)
        data[day], data[month], data[year], data[hour], data[minute], data[second] = s

    if packet_ID == power[ID]:

        packet_data = ser.read(power[size] - 4)
        s = struct.unpack('<ff', packet_data)
        data[voltage] = data[voltage]*(1-adc_smoothing_factor) + adc_linear_correction(s[0], adc_cal_voltage)*adc_smoothing_factor

        if adc_linear_correction(s[1], adc_cal_current) > current_threshold_filter:
            data[current] = data[current]*(1-adc_smoothing_factor) + adc_linear_correction(s[1], adc_cal_current)*adc_smoothing_factor
        else:
            data[current] = data[current]*(1-adc_smoothing_factor)  

# Stabilisce l'ID del pacchetto ricevuto e lo passa come argomento alla funzione di decodifica.

def update_data():
    
    while True:

        try:
            # Legge l'ID del pacchetto, ovvero i primi 4 byte
            packet_ID_bytes = ser.read(4)
            packet_ID = struct.unpack('<I', packet_ID_bytes)[0]  # Interpreta i 4 byte come un intero
             
            # Decodifica il pacchetto
            decode_packet(packet_ID)
        except: pass
        
# Definiti font e temi

with dpg.font_registry():
    font1 = dpg.add_font("brass-mono-bold.ttf", 18)

with dpg.theme(tag="PL-T"):
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 3, category=dpg.mvThemeCat_Plots)

with dpg.theme(tag="LOG-B-theme"):
    with dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (239,83,80,150))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (239,83,80,200))

with dpg.theme(tag="LOG-B-REC-theme"):
    with dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (239,83,80,255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (239,83,80,150))

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
    except: pass
    port_select(dpg.get_value("PORT-C"))

def port_button_callback():
    ports = sorted(serial.tools.list_ports.comports())
    dpg.configure_item("PORT-C", items=[port[0] for port in ports])

# Creazione e configurazione finestra dei dati in diretta. Non richiede siano già stati ricevuti i dati da inserire.

def data_table_create():
    
    with dpg.window(label="Tabella dati", height=screen_height, width=screen_width/4):

        left_item_width = screen_width/4*0.705
        rigth_item_width = screen_width/4*0.225

        # Selezione porta

        with dpg.group(horizontal=True):
            dpg.add_combo(width=left_item_width, height_mode=dpg.mvComboHeight_Small, tag="PORT-C", callback=port_callback)
            dpg.add_button(tag="PORT-B", label="AGGIORNA", width=rigth_item_width, callback=port_button_callback)

        # Controlli dei log

        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="LOG-N", default_value="Filename...", width=left_item_width)
            dpg.add_button(tag="LOG-B", label="START LOG", width=rigth_item_width, callback=log_button_callback)
            dpg.bind_item_theme("LOG-B", "LOG-B-theme")

        # Tabella dei dati

        with dpg.table(header_row=False, row_background=True,
                       borders_innerH=True, borders_outerH=True, borders_innerV=True,
                       borders_outerV=True):

            dpg.add_table_column()
            dpg.add_table_column()

            for i in range(len(data)):
                with dpg.table_row():
                    dpg.add_text(data_label[i])
                    data_text = dpg.add_text("-", tag=f"DT{i}")
                    dpg.bind_item_font(data_text, font1)

# Funzione di callback chiamata a selezione avvenuta del dato da diagrammare. Gli argomenti sono: sender (contiene il tag dell'elemento che ha chiamato la callback, gestito automaticamente dall'API), app_data (contiene la stringa selezionata, gestito automaticamente dall'API) e user_data (argomento specificato alla chiamata che contiene l'ID del plot da cui arriva la callback).
# Azzera gli assi del plot relativo. Non richiede siano già stati ricevuti dati.

def plot_selection_callback(sender, app_data, user_data):
    global plot_data_x, plot_data_y, plot_data_ID

    if sender == f"PL{user_data}-C":
        plot_data_ID[user_data] = data_label.index(app_data)
        plot_data_x[user_data] = []
        plot_data_y[user_data] = []
        dpg.delete_item(f"PL{user_data}-YA-serie")
        dpg.add_line_series(plot_data_x[user_data], plot_data_y[user_data], label=data_label[plot_data_ID[user_data]], parent=f"PL{user_data}-YA", tag=f"PL{user_data}-YA-serie")
        dpg.configure_item(f"PL{user_data}-YA", label=data_label[plot_data_ID[user_data]])
        dpg.bind_item_theme(f"PL{user_data}-YA-serie", "PL-T")

# Funzione di callback dei bottoni di controllo dei plot. 

def plot_button_callback(sender, app_data, user_data):
    global marker_i

    # Tasto di sync (pareggia la dimensione del buffer in tutti i plot).

    if sender == f"PL{user_data}-S":
        for plot_ID in range(len(plot_data_x)):
            if not plot_ID == user_data:
                dpg.set_value(f"PL{plot_ID}-B", dpg.get_value(f"PL{user_data}-B"))

    # Tasto di aggiunta dei marker.
    
    if sender.startswith("PL") and sender.endswith("-M"):

        marker_i +=1
        
        for plot_ID in range(len(plot_data_x)):
            dpg.add_plot_annotation(parent=f"PL{plot_ID}", label=f"M{marker_i}", default_value=(plot_data_x[plot_ID][-1], plot_data_y[plot_ID][-1]), color=marker_colors[random.randint(0, len(marker_colors)-1)])

# Creazione del plot, con argomento l'ID del plot da creare. Ogni volta che la funzione è chiamata viene generato il plot relativo al dato ID.
# Generare i plot con ID progressivo !!!

def plot_create(plot_ID):
    global plot_data_x, plot_data_y, plot_data_ID

    plot_data_x.append([])
    plot_data_y.append([])
    plot_data_ID.append(11)
    
    with dpg.window(label=f"Diagramma in tempo reale #{plot_ID}", pos=[screen_width/4, plot_ID*screen_height/2], height=screen_height/2, width=screen_width*0.75):

        with dpg.group(horizontal=True):
            dpg.add_combo(data_label, width=200, height_mode=dpg.mvComboHeight_Small, tag=f"PL{plot_ID}-C", default_value=data_label[plot_data_ID[plot_ID]], callback=plot_selection_callback, user_data=plot_ID)
            dpg.add_radio_button(items=("Manuale","Completo", "Insegui"), horizontal=True, default_value="Completo", tag=f"PL{plot_ID}-RB")
            dpg.add_slider_int(label="Buffer", tag=f"PL{plot_ID}-B", default_value=1000, min_value=100, max_value=5000, width=200)
            dpg.add_button(tag=f"PL{plot_ID}-S", label="Sync", callback=plot_button_callback, user_data=plot_ID)
            dpg.add_button(tag=f"PL{plot_ID}-M", label="Marker", callback=plot_button_callback, user_data=plot_ID)
            global marker_i
            marker_i = 0
            
        with dpg.plot(tag=f"PL{plot_ID}", height=screen_height/2.5, width=screen_width*0.74):

            dpg.add_plot_axis(dpg.mvXAxis, label=" ", tag=f"PL{plot_ID}-XA", time=True)
            dpg.add_plot_axis(dpg.mvYAxis, label=data_label[plot_data_ID[plot_ID]], tag=f"PL{plot_ID}-YA")

            dpg.add_line_series(plot_data_x[plot_ID], plot_data_y[plot_ID], label=data_label[plot_data_ID[plot_ID]], parent=f"PL{plot_ID}-YA", tag=f"PL{plot_ID}-YA-serie")
            dpg.bind_item_theme(f"PL{plot_ID}-YA-serie", "PL-T")

# Funzione di log. Gestisce anche il lampeggio del pulsante di registrazione.

def log_data():
    global logging

    time_label = "Ora [hh:mm:ss]"
    header_labels = [time_label] + data_label[:]

    time_data = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    data_row = [time_data] + data[:]

    if not hasattr(log_data, 'prev_time'):
        log_data.prev_time = time.time()
        log_data.blink_status = True
    
    if logging:

        folder = "logs/"
        filename = folder + dpg.get_value("LOG-N")

        if not os.path.exists(folder):
            os.makedirs(folder)
        
        if not os.path.exists(filename):
            with open(filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(header_labels)
        
        with open(filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(data_row)

        if time.time() - log_data.prev_time > 1:
            if log_data.blink_status:
                dpg.bind_item_theme("LOG-B", "LOG-B-theme")
            else:
                dpg.bind_item_theme("LOG-B", "LOG-B-REC-theme")
                
            log_data.blink_status = not log_data.blink_status
            log_data.prev_time = time.time()

data_table_create()
plot_create(0)
plot_create(1)

port_select(None)
threading.Thread(target=update_data).start()

dpg.setup_dearpygui()
dpg.show_viewport()

while dpg.is_dearpygui_running():

    # Aggiornamento dei dati in tabella.

    for i in range(len(data)):
        dpg.set_value(f"DT{i}", f"{data[i]:.{data_dec[i]}f}")

    # Aggiornamento dei dati dei plot, in base alla modalità di visualizzazione scelta.

    for plot_ID in range(len(plot_data_ID)):

        plot_data_y[plot_ID].append(data[plot_data_ID[plot_ID]])
        plot_data_x[plot_ID].append(time.time())

        if dpg.get_value(f"PL{plot_ID}-RB") == "Manuale":
            dpg.set_axis_limits_auto(f"PL{plot_ID}-YA")

        if dpg.get_value(f"PL{plot_ID}-RB") == "Insegui":
            if len(plot_data_x[plot_ID]) > dpg.get_value(f"PL{plot_ID}-B"):
                dpg.set_value(f"PL{plot_ID}-YA-serie", [plot_data_x[plot_ID][-dpg.get_value(f"PL{plot_ID}-B"):], plot_data_y[plot_ID][-dpg.get_value(f"PL{plot_ID}-B"):]])
            else:
                dpg.set_value(f"PL{plot_ID}-YA-serie", [plot_data_x[plot_ID], plot_data_y[plot_ID]])

        else:    
            dpg.set_value(f"PL{plot_ID}-YA-serie", [plot_data_x[plot_ID], plot_data_y[plot_ID]])

        if dpg.get_value(f"PL{plot_ID}-RB") == "Completo" or dpg.get_value(f"PL{plot_ID}-RB") == "Insegui":
            dpg.fit_axis_data(f"PL{plot_ID}-XA")
            dpg.set_axis_limits(f"PL{plot_ID}-YA", min(plot_data_y[plot_ID])-abs(0.1*max(plot_data_y[plot_ID])), max(plot_data_y[plot_ID])+abs(0.1*max(plot_data_y[plot_ID])))

        log_data()
                        
    dpg.render_dearpygui_frame()

dpg.destroy_context()
