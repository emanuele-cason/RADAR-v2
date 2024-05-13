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

plot1_data_y = []
plot1_data_x = []
plot1_data_ID = 11

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
    global plot1_data_x, plot1_data_y, plot1_data_ID

    if sender == "PL1-C":
        plot1_data_ID = data_label.index(app_data)
        plot1_data_x = []
        plot1_data_y = []
        dpg.delete_item("PL1-YA-serie")
        dpg.add_line_series(plot1_data_x, plot1_data_y, label=data_label[plot1_data_ID], parent="PL1-YA", tag="PL1-YA-serie")
        dpg.configure_item("PL1-YA", label=data_label[plot1_data_ID])
        dpg.bind_item_theme("PL1-YA-serie", "PL-T")

def plot_add_marker(sender, app_data, user_data):
    global marker_i
    marker_i +=1
    
    if sender == "PL1-M":
        dpg.add_plot_annotation(parent="PL1", label=f"M{marker_i}", default_value=(plot1_data_x[-1], plot1_data_y[-1]), color=marker_colors[random.randint(0, len(marker_colors)-1)])
    
    
with dpg.window(label="Real time plot #1", pos=[screen_width/4, 0], height=screen_height/2, width=screen_width*0.75):

    with dpg.theme(tag="PL-T"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvPlotStyleVar_LineWeight, 3, category=dpg.mvThemeCat_Plots)

    with dpg.group(horizontal=True):
        dpg.add_combo(data_label, width=200, height_mode=dpg.mvComboHeight_Small, tag="PL1-C", default_value=data_label[plot1_data_ID], callback=plot_data_selected)
        dpg.add_radio_button(items=("Manuale","Completo", "Insegui"), horizontal=True, default_value="Completo", tag="PL1-RB")
        dpg.add_slider_int(label="Buffer", tag="PL1-B", default_value=1000, min_value=100, max_value=5000, width=200)
        dpg.add_button(tag="PL1-M", label="Marker", callback=plot_add_marker)
        marker_i = 0
        
    with dpg.plot(tag="PL1", height=screen_height/2.5, width=screen_width*0.74):

        dpg.add_plot_axis(dpg.mvXAxis, label=" ", tag="PL1-XA", time=True)
        dpg.add_plot_axis(dpg.mvYAxis, label=data_label[plot1_data_ID], tag="PL1-YA")

        dpg.add_line_series(plot1_data_x, plot1_data_y, label=data_label[plot1_data_ID], parent="PL1-YA", tag="PL1-YA-serie")
        dpg.bind_item_theme("PL1-YA-serie", "PL-T")

dpg.setup_dearpygui()
dpg.show_viewport()

while dpg.is_dearpygui_running():

    for i in range(len(data)):
        dpg.set_value(f"DT{i}", f"{data[i]:.{data_dec[i]}f}")

    plot1_data_y.append(data[plot1_data_ID])
    plot1_data_x.append(time.time())

    if dpg.get_value("PL1-RB") == "Manuale":
        dpg.set_axis_limits_auto("PL1-YA")

    if dpg.get_value("PL1-RB") == "Insegui":
        if len(plot1_data_x) > dpg.get_value("PL1-B"):
            dpg.set_value('PL1-YA-serie', [plot1_data_x[-dpg.get_value("PL1-B"):], plot1_data_y[-dpg.get_value("PL1-B"):]])
        else:
            dpg.set_value('PL1-YA-serie', [plot1_data_x, plot1_data_y])

    else:    
        dpg.set_value('PL1-YA-serie', [plot1_data_x, plot1_data_y])

    if dpg.get_value("PL1-RB") == "Completo" or dpg.get_value("PL1-RB") == "Insegui":
        dpg.fit_axis_data("PL1-XA")
        dpg.set_axis_limits("PL1-YA", min(plot1_data_y)-abs(0.1*max(plot1_data_y)), max(plot1_data_y)+abs(0.1*max(plot1_data_y)))
                    
    dpg.render_dearpygui_frame()

dpg.destroy_context()
