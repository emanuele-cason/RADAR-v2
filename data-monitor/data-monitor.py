import serial
import struct

import threading

import dearpygui.dearpygui as dpg

# Proprietà del pacchetto: [ID, dimensione in byte].
# La dimensione deve essere quella del pacchetto con ID compreso (ovvero così come arriva dalla ground station).
ID = 0
size = 1
gps_loc = [1, 28]
gps_clk = [2, 28]
power = [3, 12]

ser = serial.Serial('COM8', 500000)

# Dati ricevuti via radio
data = [None]*14
data_label = [""]*14
nSat, lat, lon, alt, speed, cog, day, month, year, hour, minute, second, voltage, current = range(14)
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

input()

dpg.create_context()
dpg.create_viewport(title='LIFTUP Data Monitor', width=600, height=600)

with dpg.window(label="Data table"):

    with dpg.table(header_row=False, row_background=True,
                   borders_innerH=True, borders_outerH=True, borders_innerV=True,
                   borders_outerV=True):

        dpg.add_table_column()
        dpg.add_table_column()

        for i in range(len(data)):
            with dpg.table_row():
                dpg.add_text(data_label[i])
                dpg.add_text("-", tag=f"DT{i}")

dpg.setup_dearpygui()
dpg.show_viewport()

while dpg.is_dearpygui_running():

    for i in range(len(data)):
        dpg.set_value(f"DT{i}", data[i])
                    
    dpg.render_dearpygui_frame()

dpg.destroy_context()
