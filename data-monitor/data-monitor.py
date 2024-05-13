import serial
import struct

import threading
import time
import random

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

ser = serial.Serial('COM8', 500000)

# Dati ricevuti via radio
data = [0]*14
data_label = [""]*14
nSat, lat, lon, alt, speed, cog, day, month, year, hour, minute, second, voltage, current = range(14)
data_dec = [0,6,6,2,2,0,0,0,0,0,0,0,2,2]
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

# Dati dei plot
marker_colors = [
    [102,187,106, 255],    # Verde
    [66,165,245, 255],    # Blu
    [239,83,80, 255],    # Rosso
    [255,202,40, 255],  # Giallo
    [171,71,188, 255],  # Viola
]

plot_data_y = []
plot_data_x = []
plot_data_ID = []

# I pacchetti sono interpretati dalla variabile ID (già decodificata) in poi. Per questo alla dimensione del pacchetto
# originale si sottrae 4 (4 byte dell'integer ID)
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
        data[voltage], data[current] = s

def update_data():
    while True:
        # Legge l'ID del pacchetto, ovvero i primi 4 byte
        packet_ID_bytes = ser.read(4)
        packet_ID = struct.unpack('<I', packet_ID_bytes)[0]  # Interpreta i 4 byte come un intero
         
        # Decodifica il pacchetto
        decode_packet(packet_ID)

threading.Thread(target=update_data).start()

dpg.create_context()
dpg.create_viewport(title='LIFTUP Data Monitor', width=600, height=600)

with dpg.font_registry():
    font1 = dpg.add_font("brass-mono-bold.ttf", 18)

with dpg.window(label="Data table", height=screen_height, width=screen_width/4):

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

def plot_data_selected(sender, app_data, user_data):
    global plot_data_x, plot_data_y, plot_data_ID

    if sender == f"PL{user_data}-C":
        plot_data_ID[user_data] = data_label.index(app_data)
        plot_data_x[user_data] = []
        plot_data_y[user_data] = []
        dpg.delete_item(f"PL{user_data}-YA-serie")
        dpg.add_line_series(plot_data_x[user_data], plot_data_y[user_data], label=data_label[plot_data_ID[user_data]], parent=f"PL{user_data}-YA", tag=f"PL{user_data}-YA-serie")
        dpg.configure_item(f"PL{user_data}-YA", label=data_label[plot_data_ID[user_data]])
        dpg.bind_item_theme(f"PL{user_data}-YA-serie", "PL-T")

def plot_button_callback(sender, app_data, user_data):
    global marker_i

    if sender == f"PL{user_data}-S":
        for plot_ID in range(len(plot_data_x)):
            if not plot_ID == user_data:
                dpg.set_value(f"PL{plot_ID}-B", dpg.get_value(f"PL{user_data}-B"))
    
    if sender.startswith("PL") and sender.endswith("-M"):

        marker_i +=1
        
        for plot_ID in range(len(plot_data_x)):
            dpg.add_plot_annotation(parent=f"PL{plot_ID}", label=f"M{marker_i}", default_value=(plot_data_x[plot_ID][-1], plot_data_y[plot_ID][-1]), color=marker_colors[random.randint(0, len(marker_colors)-1)])

with dpg.theme(tag="PL-T"):
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 3, category=dpg.mvThemeCat_Plots)

def plot_create(plot_ID):
    global plot_data_x, plot_data_y, plot_data_ID

    plot_data_x.append([])
    plot_data_y.append([])
    plot_data_ID.append(11)
    
    with dpg.window(label=f"Real time plot #{plot_ID}", pos=[screen_width/4, plot_ID*screen_height/2], height=screen_height/2, width=screen_width*0.75):

        with dpg.group(horizontal=True):
            dpg.add_combo(data_label, width=200, height_mode=dpg.mvComboHeight_Small, tag=f"PL{plot_ID}-C", default_value=data_label[plot_data_ID[plot_ID]], callback=plot_data_selected, user_data=plot_ID)
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

plot_create(0)
plot_create(1)

dpg.setup_dearpygui()
dpg.show_viewport()

while dpg.is_dearpygui_running():

    for i in range(len(data)):
        dpg.set_value(f"DT{i}", f"{data[i]:.{data_dec[i]}f}")

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
                        
    dpg.render_dearpygui_frame()

dpg.destroy_context()
