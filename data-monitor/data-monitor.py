import serial
import struct

import tkinter as tk
import threading
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import time

# Proprietà del pacchetto: [ID, dimensione in byte].
# La dimensione deve essere quella del pacchetto con ID compreso (ovvero così come arriva dalla ground station).
ID = 0
size = 1
gps_loc = [1, 28]
gps_clk = [2, 28]
power = [3, 12]

# Interfaccia
grid_labels = ["Latitudine", "Longitudine", "Altitudine [m]", "Velocità [km/h]", "Rotta", "Fix satelliti", "Tensione [V]", "Corrente [A]"]
margin = 40
cell_width = 250
cell_height = 80
rows = 5
columns = 2
refresh_rate = 100

ser = serial.Serial('COM8', 115200)
rx_started = False

# I pacchetti sono interpretati dalla variabile ID (già decodificata) in poi. Per questo alla dimensione del pacchetto
# originale si sottrae 4 (4 byte dell'integer ID)
def decode_packet(packet_ID):
    
    if packet_ID == gps_loc[ID]:

        packet_data = ser.read(gps_loc[size] - 4)
        s = struct.unpack('<Ifffff', packet_data)
        global nSat, lat, lon, alt, speed, cog
        nSat, lat, lon, alt, speed, cog = s
        rx_started = True
        
    if packet_ID == gps_clk[ID]:

        packet_data = ser.read(gps_clk[size] - 4)
        s = struct.unpack('<IIIIII', packet_data)
        global day, month, year, hour, minute, second
        day, month, year, hour, minute, second = s

    if packet_ID == power[ID]:

        packet_data = ser.read(power[size] - 4)
        s = struct.unpack('<ff', packet_data)
        global voltage, current
        voltage, current = s

def update_data():
    while True:
        # Legge l'ID del pacchetto, ovvero i primi 4 byte
        packet_ID_bytes = ser.read(4)
        packet_ID = struct.unpack('<I', packet_ID_bytes)[0]  # Interpreta i 4 byte come un intero
         
        # Decodifica il pacchetto
        decode_packet(packet_ID)

class GridInterface:

    def __init__(self, root, rows, columns):
        self.root = root
        self.rows = rows
        self.columns = columns
        self.cell_buttons = [[None] * columns for _ in range(rows)]
        self.build_grid()

        self.root.title("Dati in tempo reale")
        window_width = columns * (cell_width + margin) + margin
        window_height = rows * (cell_height + margin) + margin
        self.root.geometry("{}x{}".format(window_width, window_height))

    def build_grid(self):
        # Crea una griglia 2D di bottoni
        for i in range(self.rows):
            for j in range(self.columns):
                # Calcola le coordinate x e y della cella
                x = j * (cell_width + margin) + margin
                y = i * (cell_height + margin) + margin
                
                # Aggiungi valore numerico grande
                value = i * self.columns + j
                button = tk.Button(self.root, text=" - ", font=("Arial", 40), command=lambda row=i, col=j: self.print_value(row, col))
                button.place(x=x, y=y, width=cell_width, height=cell_height)
                self.cell_buttons[i][j] = button

                # Aggiungi etichetta piccola
                if value in range(len(grid_labels)):
                    label = tk.Label(self.root, text=grid_labels[value], font=("Arial", 10))
                else: label = tk.Label(self.root, text=" - ", font=("Arial", 10))
                label.place(x=x, y=y + cell_height, width=cell_width, height=20)

        self.update_grid()

    def update_cell_value(self, row, column, new_value):
        # Aggiorna il valore della cella specificata
        self.cell_buttons[row][column].config(text="{:.{}f}".format(new_value, 4))

    def update_grid(self):
        self.update_cell_value(0,0,lat)
        self.update_cell_value(0,1,lon)
        self.update_cell_value(1,0,alt)
        self.update_cell_value(1,1,speed)
        self.update_cell_value(2,0,cog)
        self.update_cell_value(2,1,nSat)
        self.update_cell_value(3,0,voltage)
        self.update_cell_value(3,1,current)
        self.root.after(refresh_rate, self.update_grid)

    def print_value(self, row, column):
        # Stampa il valore della cella specificata
        print("Valore della cella ({}, {})".format(row, column))

class GraphInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Grafico in Tempo Reale")
        self.root.geometry("800x600")

        # Frame per il grafico
        self.graph_frame = ttk.Frame(self.root)
        self.graph_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Grafico
        self.figure = plt.Figure(figsize=(6, 4))
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Avvia l'aggiornamento del grafico
        self.update_graph()

    def update_graph(self):
        # Funzione per aggiornare il grafico con dati casuali
        x = time.time()
        y = second
        self.ax.plot(x, y, 'bo')
        self.ax.set_title("Grafico in Tempo Reale")
        self.ax.set_xlabel("Tempo")
        self.ax.set_ylabel("Dato")
        self.canvas.draw()
        self.root.after(100, self.update_graph)  # Richiama la funzione ogni secondo

def build_grid_window():
    root = tk.Tk()
    GridInterface(root, rows, columns)
    root.mainloop()


def build_graph_window():
    root = tk.Tk()
    GraphInterface(root)
    root.mainloop()
        
threading.Thread(target=update_data).start()
input()
build_grid_window()
build_graph_window()
