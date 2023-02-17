# GUI/Monitoring Software for the LVHV Boxes
# Coded by Isaiah Wardlaw
import os
import readline
import atexit
import queue
import logging
import serial
import matplotlib
import sys
from commands import *
import cmd2
import socket
import json
from client import *
import numpy as np


from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QWidget,
    QTabWidget,
    QGridLayout,
    QTableWidget,
    QLabel,
    QMainWindow,
)
from PyQt5 import QtCore

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

os.environ["DISPLAY"] = ':0'
background_color='background-color: white;'
button_color='background-color: white;'

class Window(QMainWindow):
    def __init__(self,test,socket):
        super(Window,self).__init__()

        self.v48=[0 for i in range(6)]
        self.i48=[0 for i in range(6)]
        self.T48=[0 for i in range(6)]
        self.hv_v=[0 for i in range(12)]
        self.hv_i=[0 for i in range(12)]

        self.test = test

        if not test:
          self.socket=socket

        #window.setCursor(PyQt5.BlankCursor)
        self.setWindowTitle("LVHV GUI")
        self.setStyleSheet(background_color)

        self.initialize_data()
        self.tabs()

        self.showFullScreen()

    # calls all of the tab initialization functions
    def tabs(self):
        self.tabs=QTabWidget()

        self.plotting=QWidget()
        self.plotting.layout=QGridLayout()
        self.plotting_tabs=QTabWidget()

        # initialize tables
        self.controls_setup()


        # initialize hv controls
        self.lv_controls_setup()


        # initialize hv controls setup
        self.hv_controls_setup()

        # initialize blade plotting Window
        self.blade_plotting_setup()

        # initialize hv plotting Window
        self.hv_plotting_setup()

        # adds tabs to the overall GUI
        self.tabs.addTab(self.tab1,"Tables")

        self.tabs.addTab(self.tab2,"LV Actuation")


        self.tabs.addTab(self.tab3,"HV Actuation")

        self.tabs.addTab(self.plotting,"Plots")

        #self.tabs.addTab(self.misc_functions,"Misc")

        self.plotting_tabs.addTab(self.tab4,"Blade Plots")
        #self.plotting_tabs.addTab(self.tab5,"Board Plots")
        self.plotting_tabs.addTab(self.tab6,"HV Plots")

        self.plotting.layout.addWidget(self.plotting_tabs)
        self.plotting.setLayout(self.plotting.layout)


        # set title and place tab widget for pyqt
        self.setWindowTitle("LVHV GUI")
        self.setCentralWidget(self.tabs)

        self.show()



     # sets up initial tables with "N/A" values
    def controls_setup(self):
        self.tab1=QWidget()
        self.tab1.layout=QGridLayout()
        self.tab1.layout.setContentsMargins(20,20,20,20)

        # setup blade table
        self.blade_control_table=QTableWidget()
        self.blade_control_table.setRowCount(6)
        self.blade_control_table.setColumnCount(3)
        self.blade_control_table.setFixedWidth(550)
        self.blade_control_table.setDisabled(True)

        self.blade_control_table.setHorizontalHeaderLabels(["Voltage (V)","current (A)","Temp (C)"])
        self.blade_control_table.setVerticalHeaderLabels(["Ch 0","Ch 1","Ch 2","Ch 3","Ch 4","Ch 5"])

        # setup hv table
        self.hv_control_table=QTableWidget()
        self.hv_control_table.setRowCount(12)
        self.hv_control_table.setColumnCount(2)
        self.hv_control_table.setFixedWidth(550)
        self.hv_control_table.setDisabled(True)
        for i in range(0,12):
            self.hv_control_table.setRowHeight(i,24)

        self.hv_control_table.setVerticalHeaderLabels(["Ch 0","Ch 1","Ch 2","Ch 3","Ch 4","Ch 5","Ch 6","Ch 7","Ch 8","Ch 9","Ch 10","Ch 11"])
        self.hv_control_table.setHorizontalHeaderLabels(["Voltage (V)","Current (mu-A)"])


        # set up tabs to select whether to view blade data or board data
        self.table_tabs=QTabWidget()
        self.table_tab1=QWidget()
        self.table_tab1.layout=QGridLayout()
        self.table_tab3=QWidget()
        self.table_tab3.layout=QGridLayout()
        self.table_tabs.addTab(self.table_tab1,"Blade Data")
        self.table_tabs.addTab(self.table_tab3,"HV Data")

        # add table widgets to tab container
        self.table_tab1.layout.addWidget(self.blade_control_table,0,0)
        self.table_tab1.setLayout(self.table_tab1.layout)

        self.table_tab3.layout.addWidget(self.hv_control_table,0,0)
        self.table_tab3.setLayout(self.table_tab3.layout)

        for i in range(6):
            # fill with blade voltage entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.blade_voltage_entries.append(current_entry)
            self.blade_control_table.setCellWidget(i,0,current_entry)

            # fill with blade current entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.blade_current_entries.append(current_entry)
            self.blade_control_table.setCellWidget(i,1,current_entry)

            # fill with blade temperature entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.blade_temperature_entries.append(current_entry)
            self.blade_control_table.setCellWidget(i,2,current_entry)

        # fill board table with entries and set background color
        self.board_5v_voltage_entries=[]
        self.board_5v_current_entries=[]
        self.board_cond_voltage_entries=[]
        self.board_cond_current_entries=[]



        # fill board table with entries and set background color
        self.hv_voltage_entries=[]
        self.hv_current_entries=[]

        for i in range(12):
            # fill with hv voltage entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.hv_voltage_entries.append(current_entry)
            self.hv_control_table.setCellWidget(i,0,current_entry)

            # fill with hv current entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.hv_current_entries.append(current_entry)
            self.hv_control_table.setCellWidget(i,1,current_entry)

        # add tab container to table_box
        self.table_box=QWidget()
        self.table_box.layout=QGridLayout()
        self.table_box.layout.addWidget(self.table_tabs,0,1)
        self.table_box.setLayout(self.table_box.layout)

        self.tab1.layout.addWidget(self.table_box,0,0)

        self.tab1.setLayout(self.tab1.layout)


    # sets up the lv control tab for the GUI
    def lv_controls_setup(self):
        self.tab2=QWidget()
        self.tab2.layout=QGridLayout()

        # initialize lv control buttons and indicators
        self.lv_power_button_1=QPushButton("LV 0")
        self.lv_power_button_1.setFixedSize(QSize(210, 130))
        self.lv_power_button_1.setStyleSheet('background-color: red')
        self.lv_power_button_1.setFont(QFont("Arial", 45))

        self.lv_power_button_2=QPushButton("LV 1")
        self.lv_power_button_2.setFixedSize(QSize(210, 130))
        self.lv_power_button_2.setStyleSheet('background-color: red')
        self.lv_power_button_2.setFont(QFont("Arial", 45))

        self.lv_power_button_3=QPushButton("LV 2")
        self.lv_power_button_3.setFixedSize(QSize(210, 130))
        self.lv_power_button_3.setStyleSheet('background-color: red')
        self.lv_power_button_3.setFont(QFont("Arial", 45))

        self.lv_power_button_4=QPushButton("LV 3")
        self.lv_power_button_4.setFixedSize(QSize(210, 130))
        self.lv_power_button_4.setStyleSheet('background-color: red')
        self.lv_power_button_4.setFont(QFont("Arial", 45))

        self.lv_power_button_5=QPushButton("LV 4")
        self.lv_power_button_5.setFixedSize(QSize(210, 130))
        self.lv_power_button_5.setStyleSheet('background-color: red')
        self.lv_power_button_5.setFont(QFont("Arial", 45))

        self.lv_power_button_6=QPushButton("LV 5")
        self.lv_power_button_6.setFixedSize(QSize(210, 130))
        self.lv_power_button_6.setStyleSheet('background-color: red')
        self.lv_power_button_6.setFont(QFont("Arial", 45))

        # add lv power buttons to layout
        self.tab2.layout.addWidget(self.lv_power_button_1,0,0)
        self.tab2.layout.addWidget(self.lv_power_button_2,0,1)
        self.tab2.layout.addWidget(self.lv_power_button_3,0,2)
        self.tab2.layout.addWidget(self.lv_power_button_4,1,0)
        self.tab2.layout.addWidget(self.lv_power_button_5,1,1)
        self.tab2.layout.addWidget(self.lv_power_button_6,1,2)

        # connect lv power buttons to actuate_lv_power()
        self.lv_power_button_1.clicked.connect(lambda: self.actuate_lv_power(0))
        self.lv_power_button_2.clicked.connect(lambda: self.actuate_lv_power(1))
        self.lv_power_button_3.clicked.connect(lambda: self.actuate_lv_power(2))
        self.lv_power_button_4.clicked.connect(lambda: self.actuate_lv_power(3))
        self.lv_power_button_5.clicked.connect(lambda: self.actuate_lv_power(4))
        self.lv_power_button_6.clicked.connect(lambda: self.actuate_lv_power(5))

        self.tab2.setLayout(self.tab2.layout)


    # called when one of the lv power buttons is pressed
    def actuate_lv_power(self,number):
        indicators=[self.lv_power_button_1,self.lv_power_button_2,self.lv_power_button_3,self.lv_power_button_4,
        self.lv_power_button_5,self.lv_power_button_6]

        if self.blade_power[number]==True:
            indicators[number].setStyleSheet('background-color: red')
            self.blade_power[number]=False

            if not self.test:
                data= {
                    "type" : 0,
                    "cmdname": "powerOff",
                    "args" : [number]
                }

                serialized = json.dumps(data)
                msg = f"{len(serialized):<{10}}"

                self.socket.send(bytes(msg,"utf-8"))
                self.socket.sendall(bytes(serialized,"utf-8"))

                data= {
                    "type" : 0,
                    "cmdname": "powerOn",
                    "args" : [None]
                }

                serialized = json.dumps(data)
                msg = f"{len(serialized):<{10}}"

                self.socket.send(bytes(msg,"utf-8"))
                self.socket.sendall(bytes(serialized,"utf-8"))
        else:
            indicators[number].setStyleSheet('background-color: green')
            self.blade_power[number]=True

            if not self.test:
                data= {
                    "type" : 0,
                    "cmdname": "powerOn",
                    "args" : [number]
                }

                serialized = json.dumps(data)
                msg = f"{len(serialized):<{10}}"

                self.socket.send(bytes(msg,"utf-8"))
                self.socket.sendall(bytes(serialized,"utf-8"))

                data= {
                    "type" : 0,
                    "cmdname": "powerOn",
                    "args" : [None]
                }

                serialized = json.dumps(data)
                msg = f"{len(serialized):<{10}}"

                self.socket.send(bytes(msg,"utf-8"))
                self.socket.sendall(bytes(serialized,"utf-8"))

    # called when one of the hv power buttons is pressed
    def actuate_hv_power(self,number):
        indicators=[self.hv_power_button_1,self.hv_power_button_2,self.hv_power_button_3,
        self.hv_power_button_4,self.hv_power_button_5,self.hv_power_button_6,
        self.hv_power_button_7,self.hv_power_button_8,self.hv_power_button_9,
        self.hv_power_button_10,self.hv_power_button_11,self.hv_power_button_12]

        if self.hv_power[number]==True:
            if number > 5:
                hv_type=1
            else:
                hv_type=0

            self.hv_power[number]=False
            indicators[number].setStyleSheet('background-color: red')

            if not self.test:
                data= {
                    "type" : hv_type,
                    "cmdname": "downHV",
                    "args" : [number]
                }

                serialized = json.dumps(data)
                msg = f"{len(serialized):<{10}}"

                self.socket.send(bytes(msg,"utf-8"))
                self.socket.sendall(bytes(serialized,"utf-8"))

        else:
            if number > 5:
                hv_type=1
            else:
                hv_type=0

            self.hv_power[number]=True
            indicators[number].setStyleSheet('background-color: green')

            if not self.test:
                data= {
                    "type" : hv_type,
                    "cmdname": "rampHV",
                    "args" : [number,1500]
                }

                serialized = json.dumps(data)
                msg = f"{len(serialized):<{10}}"

                self.socket.send(bytes(msg,"utf-8"))
                self.socket.sendall(bytes(serialized,"utf-8"))

    # sets up the hv control tab for the GUI
    def hv_controls_setup(self):
        self.tab3=QWidget()
        self.tab3.layout=QGridLayout()

        # initilize hv control buttons
        self.hv_power_button_1=QPushButton("HV 0")
        self.hv_power_button_1.setFixedSize(QSize(130, 80))
        self.hv_power_button_1.setStyleSheet('background-color: red')
        self.hv_power_button_1.setFont(QFont("Arial", 30))

        self.hv_power_button_2=QPushButton("HV 1")
        self.hv_power_button_2.setFixedSize(QSize(130, 80))
        self.hv_power_button_2.setStyleSheet('background-color: red')
        self.hv_power_button_2.setFont(QFont("Arial", 30))

        self.hv_power_button_3=QPushButton("HV 2")
        self.hv_power_button_3.setFixedSize(QSize(130, 80))
        self.hv_power_button_3.setStyleSheet('background-color: red')
        self.hv_power_button_3.setFont(QFont("Arial", 30))

        self.hv_power_button_4=QPushButton("HV 3")
        self.hv_power_button_4.setFixedSize(QSize(130, 80))
        self.hv_power_button_4.setStyleSheet('background-color: red')
        self.hv_power_button_4.setFont(QFont("Arial", 30))

        self.hv_power_button_5=QPushButton("HV 4")
        self.hv_power_button_5.setFixedSize(QSize(130, 80))
        self.hv_power_button_5.setStyleSheet('background-color: red')
        self.hv_power_button_5.setFont(QFont("Arial", 30))

        self.hv_power_button_6=QPushButton("HV 5")
        self.hv_power_button_6.setFixedSize(QSize(130, 80))
        self.hv_power_button_6.setStyleSheet('background-color: red')
        self.hv_power_button_6.setFont(QFont("Arial", 30))

        self.hv_power_button_7=QPushButton("HV 6")
        self.hv_power_button_7.setFixedSize(QSize(130, 80))
        self.hv_power_button_7.setStyleSheet('background-color: red')
        self.hv_power_button_7.setFont(QFont("Arial", 30))

        self.hv_power_button_8=QPushButton("HV 7")
        self.hv_power_button_8.setFixedSize(QSize(130, 80))
        self.hv_power_button_8.setStyleSheet('background-color: red')
        self.hv_power_button_8.setFont(QFont("Arial", 30))

        self.hv_power_button_9=QPushButton("HV 8")
        self.hv_power_button_9.setFixedSize(QSize(130, 80))
        self.hv_power_button_9.setStyleSheet('background-color: red')
        self.hv_power_button_9.setFont(QFont("Arial", 30))

        self.hv_power_button_10=QPushButton("HV 9")
        self.hv_power_button_10.setFixedSize(QSize(130, 80))
        self.hv_power_button_10.setStyleSheet('background-color: red')
        self.hv_power_button_10.setFont(QFont("Arial", 30))

        self.hv_power_button_11=QPushButton("HV 10")
        self.hv_power_button_11.setFixedSize(QSize(130, 80))
        self.hv_power_button_11.setStyleSheet('background-color: red')
        self.hv_power_button_11.setFont(QFont("Arial", 30))

        self.hv_power_button_12=QPushButton("HV 11")
        self.hv_power_button_12.setFixedSize(QSize(130, 80))
        self.hv_power_button_12.setStyleSheet('background-color: red')
        self.hv_power_button_12.setFont(QFont("Arial", 30))

        # initialize hv ramp up bars
        self.hv_bar_1=QProgressBar()
        self.hv_bar_1.setFixedSize(QSize(130, 20))

        self.hv_bar_2=QProgressBar()
        self.hv_bar_2.setFixedSize(QSize(130, 20))

        self.hv_bar_3=QProgressBar()
        self.hv_bar_3.setFixedSize(QSize(130, 20))

        self.hv_bar_4=QProgressBar()
        self.hv_bar_4.setFixedSize(QSize(130, 20))

        self.hv_bar_5=QProgressBar()
        self.hv_bar_5.setFixedSize(QSize(130, 20))

        self.hv_bar_6=QProgressBar()
        self.hv_bar_6.setFixedSize(QSize(130, 20))

        self.hv_bar_7=QProgressBar()
        self.hv_bar_7.setFixedSize(QSize(130, 20))

        self.hv_bar_8=QProgressBar()
        self.hv_bar_8.setFixedSize(QSize(130, 20))

        self.hv_bar_9=QProgressBar()
        self.hv_bar_9.setFixedSize(QSize(130, 20))

        self.hv_bar_10=QProgressBar()
        self.hv_bar_10.setFixedSize(QSize(130, 20))

        self.hv_bar_11=QProgressBar()
        self.hv_bar_11.setFixedSize(QSize(130, 20))

        self.hv_bar_12=QProgressBar()
        self.hv_bar_12.setFixedSize(QSize(130, 20))

        # add hv power buttons to layout
        self.tab3.layout.addWidget(self.hv_power_button_1,1,0)
        self.tab3.layout.addWidget(self.hv_power_button_2,1,1)
        self.tab3.layout.addWidget(self.hv_power_button_3,1,2)
        self.tab3.layout.addWidget(self.hv_power_button_4,1,3)
        self.tab3.layout.addWidget(self.hv_power_button_5,3,0)
        self.tab3.layout.addWidget(self.hv_power_button_6,3,1)
        self.tab3.layout.addWidget(self.hv_power_button_7,3,2)
        self.tab3.layout.addWidget(self.hv_power_button_8,3,3)
        self.tab3.layout.addWidget(self.hv_power_button_9,5,0)
        self.tab3.layout.addWidget(self.hv_power_button_10,5,1)
        self.tab3.layout.addWidget(self.hv_power_button_11,5,2)
        self.tab3.layout.addWidget(self.hv_power_button_12,5,3)

        # add hv progress bars to layout
        self.tab3.layout.addWidget(self.hv_bar_1,0,0)
        self.tab3.layout.addWidget(self.hv_bar_2,0,1)
        self.tab3.layout.addWidget(self.hv_bar_3,0,2)
        self.tab3.layout.addWidget(self.hv_bar_4,0,3)
        self.tab3.layout.addWidget(self.hv_bar_5,2,0)
        self.tab3.layout.addWidget(self.hv_bar_6,2,1)
        self.tab3.layout.addWidget(self.hv_bar_7,2,2)
        self.tab3.layout.addWidget(self.hv_bar_8,2,3)
        self.tab3.layout.addWidget(self.hv_bar_9,4,0)
        self.tab3.layout.addWidget(self.hv_bar_10,4,1)
        self.tab3.layout.addWidget(self.hv_bar_11,4,2)
        self.tab3.layout.addWidget(self.hv_bar_12,4,3)

        #connect hv power buttons to actuate_hv_power
        self.hv_power_button_1.clicked.connect(lambda: self.actuate_hv_power(0))
        self.hv_power_button_2.clicked.connect(lambda: self.actuate_hv_power(1))
        self.hv_power_button_3.clicked.connect(lambda: self.actuate_hv_power(2))
        self.hv_power_button_4.clicked.connect(lambda: self.actuate_hv_power(3))
        self.hv_power_button_5.clicked.connect(lambda: self.actuate_hv_power(4))
        self.hv_power_button_6.clicked.connect(lambda: self.actuate_hv_power(5))
        self.hv_power_button_7.clicked.connect(lambda: self.actuate_hv_power(6))
        self.hv_power_button_8.clicked.connect(lambda: self.actuate_hv_power(7))
        self.hv_power_button_9.clicked.connect(lambda: self.actuate_hv_power(8))
        self.hv_power_button_10.clicked.connect(lambda: self.actuate_hv_power(9))
        self.hv_power_button_11.clicked.connect(lambda: self.actuate_hv_power(10))
        self.hv_power_button_12.clicked.connect(lambda: self.actuate_hv_power(11))

        self.tab3.setLayout(self.tab3.layout)

    # initializes blade plotting (exelcys)
    def blade_plotting_setup(self):
        self.tab4=QWidget()
        self.tab4.layout=QGridLayout()

        # set up the blade plot
        self.blade_plot=Figure()
        self.blade_plot_canvas=FigureCanvas(self.blade_plot)
        self.blade_plot_axes=self.blade_plot.add_subplot(111)

        self.blade_plot_axes.set_xlim([0,10])
        self.blade_plot_axes.set_ylim([0,60])
        self.blade_plot_axes.set_title('Channel 0 Blade Voltage')
        self.blade_plot_axes.set_ylabel('Voltage (V)')
        self.blade_plot_axes.set_xlabel('Iterative Age of Datapoint: each iteration is ' + 'one' + ' minute.')

        # initialize data (placed outside of bounds, so that it doesn't show up initially)
        self.blade_plot_data_x=[*range(0,10,1)]
        self.blade_plot_data=self.blade_plot_axes.plot(self.blade_plot_data_x,self.blade_voltage_plot[0],marker='o',linestyle='None',markersize=2,color='k')[0]

        # add dropdown menus to select what's plotted
        self.blade_channel_selector=QComboBox()
        self.blade_channel_selector.addItems(["Channel 0","Channel 1","Channel 2","Channel 3","Channel 4","Channel 5"])
        self.blade_channel_selector.setStyleSheet(button_color)
        self.blade_channel_selector.currentIndexChanged.connect(self.change_blade_plot)

        self.blade_measurement_selector=QComboBox()
        self.blade_measurement_selector.addItems(["Voltage","Current","Temperature"])
        self.blade_measurement_selector.setStyleSheet(button_color)
        self.blade_measurement_selector.currentIndexChanged.connect(self.change_blade_plot)

        # add widgets and set layout
        self.tab4.layout.addWidget(self.blade_channel_selector,0,0)
        self.tab4.layout.addWidget(self.blade_measurement_selector,1,0)
        self.tab4.layout.addWidget(self.blade_plot_canvas,0,1)
        self.tab4.setLayout(self.tab4.layout)

    # instantly changes what's being displayed on the main plot, depending on the user's selection
    # this function is only used when the TYPE of data that is being plotted changes, as per user input
    def change_blade_plot(self):
        channel=self.get_blade_channel()
        type=self.blade_measurement_selector.currentText()

        # update labels for the blade plot
        self.blade_plot_axes.set_title(self.blade_channel_selector.currentText() + ' Blade ' + type)
        if type=="Voltage":
            self.blade_plot_axes.set_ylabel('Voltage (V)')
        elif type=="Current":
            self.blade_plot_axes.set_ylabel('Current (A)')
        else:
            self.blade_plot_axes.set_ylabel('Temperature (C)')

        # ensure that the proper type of data is plotted
        if type=="Voltage":
            self.blade_plot_data.set_ydata(self.blade_voltage_plot[channel])
        elif type=="Current":
            self.blade_plot_data.set_ydata(self.blade_current_plot[channel])
        else:
            self.blade_plot_data.set_ydata(self.blade_temperature_plot[channel])

        # update the plot
        self.blade_plot_canvas.draw()
        self.blade_plot_canvas.flush_events()

    # initializes hv plotting
    def hv_plotting_setup(self):
        self.tab6=QWidget()
        self.tab6.layout=QGridLayout()

        # setup the hv plot
        self.hv_plot=Figure()
        self.hv_plot_canvas=FigureCanvas(self.hv_plot)
        self.hv_plot_axes=self.hv_plot.add_subplot(111)

        self.hv_plot_axes.set_xlim([0,10])
        self.hv_plot_axes.set_ylim([0,1600])
        self.hv_plot_axes.set_title('Channel 0 HV Voltage')
        self.hv_plot_axes.set_ylabel('Voltage (V)')
        self.hv_plot_axes.set_xlabel('Iterative Age of Datapoint: each iteration is ' + 'one' + ' minute.')

        # initialize data (placed outside of bounds, so that it doesn't show up initially)
        self.hv_plot_data_x=[*range(0,10,1)]
        self.hv_plot_data=self.hv_plot_axes.plot(self.hv_plot_data_x,self.hv_voltage_plot[0],marker='o',linestyle='None',markersize=2,color='k')[0]

        # add dropdown menus to select what's plotted
        self.hv_channel_selector=QComboBox()
        self.hv_channel_selector.addItems(["Channel 0","Channel 1","Channel 2","Channel 3","Channel 4","Channel 5",
        "Channel 6","Channel 7","Channel 8","Channel 9","Channel 10","Channel 11"])
        self.hv_channel_selector.setStyleSheet(button_color)
        self.hv_channel_selector.currentIndexChanged.connect(self.change_hv_plot)

        self.hv_measurement_selector=QComboBox()
        self.hv_measurement_selector.addItems(["Voltage","Current"])
        self.hv_measurement_selector.setStyleSheet(button_color)
        self.hv_measurement_selector.currentIndexChanged.connect(self.change_hv_plot)

        # add widgets and set layout
        self.tab6.layout.addWidget(self.hv_channel_selector,0,0)
        self.tab6.layout.addWidget(self.hv_measurement_selector,1,0)
        self.tab6.layout.addWidget(self.hv_plot_canvas,0,1)
        self.tab6.setLayout(self.tab6.layout)

    # called to change the hv plot
    # this function is only used when the TYPE of data that is being plotted changes, as per user input
    def change_hv_plot(self):
        channel=self.get_hv_channel()
        type=self.hv_measurement_selector.currentText()

        # update labels for the hv plot
        self.hv_plot_axes.set_title(self.hv_channel_selector.currentText() + ' HV ' + type)
        if type=="Voltage":
            self.hv_plot_axes.set_ylabel('Voltage (V)')
            self.hv_plot_axes.set_ylim([0,1600])
        else:
            self.hv_plot_axes.set_ylabel('Current (mu-A)')
            self.hv_plot_axes.set_ylim([0,100])

        # ensure that the proper type of data is being plotted
        if type=="Voltage":
            self.hv_plot_data.set_ydata(self.hv_voltage_plot[channel])
        else:
            self.hv_plot_data.set_ydata(self.hv_current_plot[channel])

        # update the plot
        self.hv_plot_canvas.draw()
        self.hv_plot_canvas.flush_events()

    # updates the blade table with recent data
    # also ensures that lv buttons are proper color
    def update_blade_table(self):
        indicators=[self.lv_power_button_1,self.lv_power_button_2,self.lv_power_button_3,self.lv_power_button_4,
        self.lv_power_button_5,self.lv_power_button_6]

        for j in range(6):
            self.blade_voltage_entries[j].setText(str(self.v48[j]))
            self.blade_current_entries[j].setText(str(self.i48[j]))
            self.blade_temperature_entries[j].setText(str(self.T48[j]))

    # updates the hv bars
    def update_hv_bars(self):
        bars=[self.hv_bar_1,self.hv_bar_2,self.hv_bar_3,self.hv_bar_4,self.hv_bar_5,self.hv_bar_6,self.hv_bar_7,
        self.hv_bar_8,self.hv_bar_9,self.hv_bar_10,self.hv_bar_11,self.hv_bar_12]

        for j in range(12):
            percentage=int(self.hv_v[j]/15)
            bars[j].setValue(percentage)

    # updates the hv table with latest available data
    def update_hv_table(self):
        indicators=[self.hv_power_button_1,self.hv_power_button_2,self.hv_power_button_3,
        self.hv_power_button_4,self.hv_power_button_5,self.hv_power_button_6,
        self.hv_power_button_7,self.hv_power_button_8,self.hv_power_button_9,
        self.hv_power_button_10,self.hv_power_button_11,self.hv_power_button_12]

        for j in range(12):
            self.hv_voltage_entries[j].setText(str(self.hv_v[j]))
            self.hv_current_entries[j].setText(str(self.hv_i[j]))

    def update_data(self):
        self.update_hv_table()
        self.update_hv_bars()
        self.update_blade_table()

     # called by the timer to update the main plot with new data
    def update_blade_plot(self):
        channel=self.get_blade_channel()
        type=self.blade_measurement_selector.currentText()

        # rotate plot lists
        for i in range(len(self.blade_voltage_plot)):
            self.blade_voltage_plot[i]=[self.v48[i]]+self.blade_voltage_plot[i][:-1]
            self.blade_current_plot[i]=[self.i48[i]]+self.blade_current_plot[i][:-1]
            self.blade_temperature_plot[i]=[self.T48[i]]+self.blade_temperature_plot[i][:-1]

        # determine what kind of data is being plotted, and respond accordingly
        if type=="Voltage":
            self.blade_plot_data.set_ydata(self.blade_voltage_plot[channel])
        elif type=="Current":
            self.blade_plot_data.set_ydata(self.blade_current_plot[channel])
        else:
            self.blade_plot_data.set_ydata(self.blade_temperature_plot[channel])

        # update the plot
        self.blade_plot_canvas.draw()
        self.blade_plot_canvas.flush_events()

     # this function updates the hv plot
    def update_hv_plot(self):
        channel=self.get_hv_channel()
        type=self.hv_measurement_selector.currentText()

        # rotate plot lists
        for i in range(len(self.hv_voltage_plot)):
            self.hv_voltage_plot[i]=[self.hv_v[i]]+self.hv_voltage_plot[i][:-1]
            self.hv_current_plot[i]=[self.hv_i[i]]+self.hv_current_plot[i][:-1]

        if type=="Voltage":
            self.hv_plot_data.set_ydata(self.hv_voltage_plot[channel])
        else:
            self.hv_plot_data.set_ydata(self.hv_current_plot[channel])
        self.hv_plot_canvas.draw()
        self.hv_plot_canvas.flush_events()

    def initialize_data(self):
        # keeps lv screen update from occuring until data is acquired
        self.initial_lv_display=True

        # initialize lists of data
        self.blade_voltage_plot=[[500]*10]*6
        self.blade_current_plot=[[500]*10]*6
        self.blade_temperature_plot=[[500]*10]*6

        self.board_5v_voltage_plot=[[500]*10]*6
        self.board_5v_current_plot=[[500]*10]*6
        self.board_cond_voltage_plot=[[500]*10]*6
        self.board_cond_current_plot=[[500]*10]*6

        self.hv_voltage_plot=[[10000]*10]*12
        self.hv_current_plot=[[10000]*10]*12

        self.stability_blade_voltage_plot=[[500]*48]*6
        self.stability_blade_current_plot=[[500]*48]*6
        self.stability_blade_temperature_plot=[[500]*48]*6

        self.stability_board_5v_voltage_plot=[[500]*48]*6
        self.stability_board_5v_current_plot=[[500]*48]*6
        self.stability_board_cond_voltage_plot=[[500]*48]*6
        self.stability_board_cond_current_plot=[[500]*48]*6

        self.stability_hv_voltage_plot=[[10000]*48]*12
        self.stability_hv_current_plot=[[10000]*48]*12

        # fill blade table with entries and set background color
        self.blade_voltage_entries=[]
        self.blade_current_entries=[]
        self.blade_temperature_entries=[]

        # keeps track of blade power statuses
        self.blade_power=[False]*6

        # keeps track of hv power statuses
        self.hv_power=[False]*12

        # vars to keep track of hv ramping
        self.is_ramping = False
        self.rampup_list=[]

        self.hv_voltage = [0]*12
        self.hv_current = [0]*12

        self.hv_board_temp=0
        self.hv_board_current=0


        self.table_update_timer = QTimer(self)
        self.table_update_timer.setSingleShot(False)
        self.table_update_timer.timeout.connect(self.update_data)
        self.table_update_timer.timeout.connect(self.update_all_data_log)
        self.table_update_timer.start(1000)


        self.plot_update_timer=QTimer(self)
        self.plot_update_timer.setSingleShot(False)
        self.plot_update_timer.timeout.connect(self.update_blade_plot)
        self.plot_update_timer.timeout.connect(self.update_hv_plot)
        self.plot_update_timer.start(60000)


    # acquires the channel being measured
    def get_blade_channel(self):
        # determine which blade data is to be plotted for
        channels={"Channel 0": 0,"Channel 1": 1,"Channel 2": 2,"Channel 3": 3,"Channel 4": 4,"Channel 5": 5}
        channel=channels[self.blade_channel_selector.currentText()]
        return channel

    # returns the proper hv channel number, based on the current user selection
    def get_hv_channel(self):
        # determine which hv channel data is to be plotted for
        channels={"Channel 0": 0,"Channel 1": 1,"Channel 2": 2,"Channel 3": 3,"Channel 4": 4,
        "Channel 5": 5,"Channel 6": 6,"Channel 7": 7,"Channel 8": 8,"Channel 9": 9,
        "Channel 10": 10,"Channel 11": 11}
        channel=channels[self.hv_channel_selector.currentText()]
        return channel

    def update_all_data_log(self):
        with open('lvdata.log', 'rb') as file0:
            try:
                file0.seek(-2, os.SEEK_END)
                while file0.read(1) != b'\n':
                    file0.seek(-2, os.SEEK_CUR)
            except OSError:
                file0.seek(0)
            lv_pre = file0.readline().decode()

        
        with open('hvdata0.log', 'rb') as file1:
            try:
                file1.seek(-2, os.SEEK_END)
                while file1.read(1) != b'\n':
                    file1.seek(-2, os.SEEK_CUR)
            except OSError:
                file1.seek(0)
            hv0_pre = file1.readline().decode()
        
        with open('hvdata1.log', 'rb') as file2:
            try:
                file2.seek(-2, os.SEEK_END)
                while file2.read(1) != b'\n':
                    file2.seek(-2, os.SEEK_CUR)
            except OSError:
                file2.seek(0)
            hv1_pre = file2.readline().decode()

        
        v48 = [float(i) for i in lv_pre.split(' ')[1:7]]
        i48 = [float(i) for i in lv_pre.split(' ')[7:13]]
        T48 = [float(i) for i in lv_pre.split(' ')[13:18] + [lv_pre.split(' ')[18][:-1]]]

        hv0_v=[]
        hv0_i=[]
        hv_current=float(hv0_pre.split(' ')[-1])
        for i in range(6):
            hv0_i.append(float(hv0_pre.split(' ')[i*2+1]))
            hv0_v.append(float(hv0_pre.split(' ')[i*2+2]))
        
        hv1_v=[]
        hv1_i=[]
        hv_current=float(hv1_pre.split(' ')[-1])
        for i in range(6):
            hv1_i.append(float(hv1_pre.split(' ')[i*2+1]))
            hv1_v.append(float(hv1_pre.split(' ')[i*2+2]))
        


        hv_v = hv0_v + hv1_v
        hv_i = hv0_i + hv1_i


        if len(hv_v) == 12:
            self.hv_v = hv_v
        if len(hv_i) == 12:
            self.hv_i = hv_i
        if len(v48) == 6:
            self.v48 = v48
        if len(i48) == 6:
            self.i48 = i48
        if len(T48) == 6:
            self.T48 = T48


## Main function
## =============

if __name__ == '__main__':
    is_test = False

    if not is_test:
        topdir = os.path.dirname(os.path.realpath(__file__))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = "127.0.0.1"
        port = 12000
        sock.connect((host,port))



        App = QApplication(sys.argv)

        window = Window(True,sock)

        gui_thread = threading.Thread(target=App.exec(), daemon = True, args=[False])
        gui_thread.start()

    else:
        sock = False
        
        App = QApplication(sys.argv)

        window = Window(True,sock)

        gui_thread = threading.Thread(target=App.exec(), daemon = True, args=[True])
        gui_thread.start()