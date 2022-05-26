import sys
import glob
import os
import json
import struct
import time
import threading
import readline

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.figure import *

import math
import rlcompleter
from pprint import pprint
import smbus
from smbus import SMBus
#import Adafruit_BBIO.GPIO as GPIO
import RPi.GPIO as GPIO
from RPiMCP23S17.MCP23S17 import MCP23S17
import random
from grafana_api.grafana_face import GrafanaFace

# ensure that the window closes on control c
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)


os.environ["DISPLAY"] = ':0'
background_color='background-color: blue;'
button_color='background-color: white;'



class Session():
    def __init__(self):
        self.voltage=None
        self.current=None
        self.temperature=None

    def power_on(self,test):
        GPIO.output(GLOBAL_ENABLE_PIN,GPIO.LOW)
        if not test:
            for ich in range(0,12):
                mcp1.digitalWrite(ich+8, MCP23S17.LEVEL_LOW)
                print("Channel " + str(ich) + " enabled")
        else:
            print("Testing Mode Enabled")

    def power_off(self,test):
        GPIO.output(GLOBAL_ENABLE_PIN,GPIO.LOW)
        if not test:
            for ich in range(0,12):
                mcp1.digitalWrite(ich+8, MCP23S17.LEVEL_LOW)
                print("Channel " + str(ich) + "disabled")
        else:
            print("Testing Mode Exited")

    def get_data(self,test):
        # acquire Voltage
        voltage_values=[]
        if not test:
            pass
        else:
            for i in range(0,6):
                voltage_values.append(round(random.uniform(35,45),3))
                # ensure delay between channel readings

        # acquire Current
        current_values=[]
        if not test:
            pass
        else:
            for i in range(0,6):
                current_values.append(round(random.uniform(10,15),3))
                # ensure delay between channel readings

        # acquire Temperature
        temperature_values=[]
        if not test:
            pass
        else:
            for i in range(0,6):
                temperature_values.append(round(random.uniform(28,35),3))
                # ensure delay between channel readings

        # acquire 5v voltage
        five_voltage=[]
        if not test:
            pass
        else:
            for i in range(0,6):
                five_voltage.append(round(random.uniform(45,52),3))

        # acquire 5v current
        five_current=[]
        if not test:
            pass
        else:
            for i in range(0,6):
                five_current.append(round(random.uniform(10,20),3))

        # acquire conditioned voltage
        cond_voltage=[]
        if not test:
            pass
        else:
            for i in range(0,6):
                cond_voltage.append(round(random.uniform(45,52),3))

        # acquire conditioned current
        cond_current=[]
        if not test:
            pass
        else:
            for i in range(0,6):
                cond_current.append(round(random.uniform(10,20),3))

        # save data lists for blades
        self.voltage=voltage_values
        self.current=current_values
        self.temperature=temperature_values

        # save data lists for board
        self.five_voltage=five_voltage
        self.five_current=five_current
        self.cond_voltage=cond_voltage
        self.cond_current=cond_current

    def save_txt(self):
        output=''
        for i in range(0,6):
            output+='ch'+str(i)
            output+=','+str(self.voltage[i])
            output+=','+str(self.current[i])
            output+=','+str(self.temperature[i])
            output+=','+str(self.five_voltage[i])
            output+=','+str(self.five_current[i])
            output+=','+str(self.cond_voltage[i])
            output+=','+str(self.cond_current[i])
            output+=','+str(time.time())
        output+='\n'

        file1=open("logfile.txt", "a")
        file1.write(output)
        file1.close()

class Window(QMainWindow,Session):
    def __init__(self):
        super(Window,self).__init__()
        self.initialize_data()
        # since it's a touch screen, the cursor is irritating
        self.setCursor(Qt.BlankCursor)

        self.setWindowTitle("LVHV GUI")

        self.setStyleSheet(background_color)

        # call function to set up the overall tab layout
        self.tabs()

        self.showFullScreen()

    def tabs(self):
        self.tabs=QTabWidget()

        # initialize control buttons
        self.controls_setup()

        # initialize blade plotting Window
        self.blade_plotting_setup()

        # initialize board plotting Window
        self.board_plotting_setup()

        # initialize diagnostics Window
        self.diagnostics_setup()

        self.tabs.addTab(self.tab1,"Controls")
        self.tabs.addTab(self.tab2,"Raw Blade Plots")
        self.tabs.addTab(self.tab3,"Board Plots")
        self.tabs.addTab(self.tab4,"Diagnostics")

        self.setWindowTitle("LVHV GUI")
        self.setCentralWidget(self.tabs)

        self.show()


    def blade_plotting_setup(self):
        self.tab2=QWidget()
        self.tab2.layout=QGridLayout()

        # set up the blade plot
        self.blade_plot=Figure()
        self.blade_plot_canvas=FigureCanvas(self.blade_plot)
        self.blade_plot_axes=self.blade_plot.add_subplot(111)

        self.blade_plot_axes.set_xlim([0,50])
        self.blade_plot_axes.set_ylim([0,100])
        self.blade_plot_axes.set_title('Channel 1 Blade Voltage')
        self.blade_plot_axes.set_ylabel('Voltage (V)')
        self.blade_plot_axes.set_xlabel('Iterative Age of Datapoint')

        # initialize data (placed outside of bounds, so that it doesn't show up initially)
        self.blade_plot_data_x=[*range(0,50,1)]
        self.blade_plot_data=self.blade_plot_axes.plot(self.blade_plot_data_x,self.blade_voltage_plot[0],marker='o',linestyle='None',markersize=2,color='k')[0]

        # add dropdown menus to select what's plotted
        self.blade_channel_selector=QComboBox()
        self.blade_channel_selector.addItems(["Channel 1","Channel 2","Channel 3","Channel 4","Channel 5","Channel 6"])
        self.blade_channel_selector.setStyleSheet(button_color)
        self.blade_channel_selector.currentIndexChanged.connect(self.change_blade_plot)

        self.blade_measurement_selector=QComboBox()
        self.blade_measurement_selector.addItems(["Voltage","Current","Temperature"])
        self.blade_measurement_selector.setStyleSheet(button_color)
        self.blade_measurement_selector.currentIndexChanged.connect(self.change_blade_plot)

        # add widgets and set layout
        self.tab2.layout.addWidget(self.blade_channel_selector,0,0)
        self.tab2.layout.addWidget(self.blade_measurement_selector,1,0)
        self.tab2.layout.addWidget(self.blade_plot_canvas,0,1)
        self.tab2.setLayout(self.tab2.layout)

    def board_plotting_setup(self):
        self.tab3=QWidget()
        self.tab3.layout=QGridLayout()

        # setup the board plot
        self.board_plot=Figure()
        self.board_plot_canvas=FigureCanvas(self.board_plot)
        self.board_plot_axes=self.board_plot.add_subplot(111)

        self.board_plot_axes.set_xlim([0,50])
        self.board_plot_axes.set_ylim([0,100])
        self.board_plot_axes.set_title('Channel 1 5V Voltage')
        self.board_plot_axes.set_ylabel('Voltage (V)')
        self.board_plot_axes.set_xlabel('Iterative Age of Datapoint')

        # initialize data (placed outside of bounds, so that it doesn't show up initially)
        self.board_plot_data_x=[*range(0,50,1)]
        self.board_plot_data=self.board_plot_axes.plot(self.board_plot_data_x,self.board_5v_voltage_plot[0],marker='o',linestyle='None',markersize=2,color='k')[0]

        # add dropdown menus to select what's plotted
        self.board_channel_selector=QComboBox()
        self.board_channel_selector.addItems(["Channel 1","Channel 2","Channel 3","Channel 4","Channel 5","Channel 6"])
        self.board_channel_selector.setStyleSheet(button_color)
        self.board_channel_selector.currentIndexChanged.connect(self.change_board_plot)

        self.board_measurement_selector=QComboBox()
        self.board_measurement_selector.addItems(["5V Voltage","5V Current","Conditioned Voltage","Conditioned Current"])
        self.board_measurement_selector.setStyleSheet(button_color)
        self.board_measurement_selector.currentIndexChanged.connect(self.change_board_plot)

        # add widgets and set layout
        self.tab3.layout.addWidget(self.board_channel_selector,0,0)
        self.tab3.layout.addWidget(self.board_measurement_selector,1,0)
        self.tab3.layout.addWidget(self.board_plot_canvas,0,1)
        self.tab3.setLayout(self.tab3.layout)



    def diagnostics_setup(self):
        self.tab4=QWidget()


    def controls_setup(self):
        self.tab1=QWidget()
        self.tab1.layout=QGridLayout()
        self.tab1.layout.setContentsMargins(20,20,20,20)

        # define buttons and indicators

        self.power_button_1=QPushButton("Blade 1 Power")
        self.power_button_1.setStyleSheet(button_color)
        self.power_indicator_1=QCheckBox()
        self.power_indicator_1.setStyleSheet('background-color: red')
        self.power_indicator_1.setDisabled(True)

        self.power_button_2=QPushButton("Blade 2 Power")
        self.power_button_2.setStyleSheet(button_color)
        self.power_indicator_2=QCheckBox()
        self.power_indicator_2.setStyleSheet('background-color: red')
        self.power_indicator_2.setDisabled(True)

        self.power_button_3=QPushButton("Blade 3 Power")
        self.power_button_3.setStyleSheet(button_color)
        self.power_indicator_3=QCheckBox()
        self.power_indicator_3.setStyleSheet('background-color: red')
        self.power_indicator_3.setDisabled(True)

        self.power_button_4=QPushButton("Blade 4 Power")
        self.power_button_4.setStyleSheet(button_color)
        self.power_indicator_4=QCheckBox()
        self.power_indicator_4.setStyleSheet('background-color: red')
        self.power_indicator_4.setDisabled(True)

        self.power_button_5=QPushButton("Blade 5 Power")
        self.power_button_5.setStyleSheet(button_color)
        self.power_indicator_5=QCheckBox()
        self.power_indicator_5.setStyleSheet('background-color: red')
        self.power_indicator_5.setDisabled(True)

        self.power_button_6=QPushButton("Blade 6 Power")
        self.power_button_6.setStyleSheet(button_color)
        self.power_indicator_6=QCheckBox()
        self.power_indicator_6.setStyleSheet('background-color: red')
        self.power_indicator_6.setDisabled(True)

        # setup blade table
        self.blade_control_table=QTableWidget()
        self.blade_control_table.setRowCount(6)
        self.blade_control_table.setColumnCount(3)
        self.blade_control_table.setFixedWidth(550)
        self.blade_control_table.setDisabled(True)

        self.blade_control_table.setHorizontalHeaderLabels(["Voltage (V)","current (A)","Temperature (C)"])
        self.blade_control_table.setVerticalHeaderLabels(["Ch 1","Ch 2","Ch 3","Ch 4","Ch 5","Ch 6"])
        self.blade_control_table.horizontalHeader().setResizeMode(QHeaderView.Stretch)

        # setup board table
        self.board_control_table=QTableWidget()
        self.board_control_table.setRowCount(6)
        self.board_control_table.setColumnCount(4)
        self.board_control_table.setFixedWidth(550)
        self.board_control_table.setDisabled(True)

        self.board_control_table.setHorizontalHeaderLabels(["5V Voltage (V)","5V Current (A)","Cond Voltage (V)","Cond Current (A)"])
        self.board_control_table.setVerticalHeaderLabels(["Ch 1","Ch 2","Ch 3","Ch 4","Ch 5","Ch 6"])
        self.board_control_table.horizontalHeader().setResizeMode(QHeaderView.Stretch)

        # set up tabs to select whether to view blade data or board data
        self.table_tabs=QTabWidget()
        self.table_tab1=QWidget()
        self.table_tab1.layout=QGridLayout()
        self.table_tab2=QWidget()
        self.table_tab2.layout=QGridLayout()
        self.table_tabs.addTab(self.table_tab1,"Blade Data")
        self.table_tabs.addTab(self.table_tab2,"Board Data")

        # add table widgets to tab container
        self.table_tab1.layout.addWidget(self.blade_control_table,0,0)
        self.table_tab1.setLayout(self.table_tab1.layout)
        self.table_tab2.layout.addWidget(self.board_control_table,0,0)
        self.table_tab2.setLayout(self.table_tab2.layout)

        # fill blade table with entries and set background color
        self.blade_voltage_entries=[]
        self.blade_current_entries=[]
        self.blade_temperature_entries=[]

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

        for i in range(6):
            # fill with board 5v voltage entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.board_5v_voltage_entries.append(current_entry)
            self.board_control_table.setCellWidget(i,0,current_entry)

            # fill with board 5v current entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.board_5v_current_entries.append(current_entry)
            self.board_control_table.setCellWidget(i,1,current_entry)

            # fill with board conditioned voltage entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.board_cond_voltage_entries.append(current_entry)
            self.board_control_table.setCellWidget(i,2,current_entry)

            # fill with board conditioned current entries
            current_entry=QLabel("N/A")
            current_entry.setAlignment(Qt.AlignCenter)
            current_entry.setStyleSheet(button_color)
            self.board_cond_current_entries.append(current_entry)
            self.board_control_table.setCellWidget(i,3,current_entry)

        # add items to tab 1 layout
        self.power_button_box=QWidget()
        self.power_button_box.layout=QGridLayout()

        # add power buttons to layout
        self.power_button_box.layout.addWidget(self.power_button_1,0,0)
        self.power_button_box.layout.addWidget(self.power_button_2,1,0)
        self.power_button_box.layout.addWidget(self.power_button_3,2,0)
        self.power_button_box.layout.addWidget(self.power_button_4,3,0)
        self.power_button_box.layout.addWidget(self.power_button_5,4,0)
        self.power_button_box.layout.addWidget(self.power_button_6,5,0)

        # add power indicators to layout
        self.power_button_box.layout.addWidget(self.power_indicator_1,0,1)
        self.power_button_box.layout.addWidget(self.power_indicator_2,1,1)
        self.power_button_box.layout.addWidget(self.power_indicator_3,2,1)
        self.power_button_box.layout.addWidget(self.power_indicator_4,3,1)
        self.power_button_box.layout.addWidget(self.power_indicator_5,4,1)
        self.power_button_box.layout.addWidget(self.power_indicator_6,5,1)

        # connect power buttons to actuate_power()
        self.power_button_1.clicked.connect(lambda: self.actuate_power(0))
        self.power_button_2.clicked.connect(lambda: self.actuate_power(1))
        self.power_button_3.clicked.connect(lambda: self.actuate_power(2))
        self.power_button_4.clicked.connect(lambda: self.actuate_power(3))
        self.power_button_5.clicked.connect(lambda: self.actuate_power(4))
        self.power_button_6.clicked.connect(lambda: self.actuate_power(5))

        self.power_button_box.setLayout(self.power_button_box.layout)

        # add tab container to table_box
        self.table_box=QWidget()
        self.table_box.layout=QGridLayout()
        self.table_box.layout.addWidget(self.table_tabs,0,1)
        self.table_box.setLayout(self.table_box.layout)

        self.tab1.layout.addWidget(self.power_button_box,0,0)
        self.tab1.layout.addWidget(self.table_box,0,1)

        self.tab1.setLayout(self.tab1.layout)

    # called when one of the power buttons is pressed
    def actuate_power(self,number):
        indicators=[self.power_indicator_1,self.power_indicator_2,self.power_indicator_3,
        self.power_indicator_4,self.power_indicator_5,self.power_indicator_6]

        if self.blade_power[number]==True:
            indicators[number].setStyleSheet('background-color: red')
            self.blade_power[number]=False
        else:
            indicators[number].setStyleSheet('background-color: green')
            self.blade_power[number]=True


    def update_blade_table(self):
        for j in range(6):
            self.blade_voltage_entries[j].setText(str(self.voltage[j]))
            self.blade_current_entries[j].setText(str(self.current[j]))
            self.blade_temperature_entries[j].setText(str(self.temperature[j]))

    def update_board_table(self):
        for j in range(6):
            self.board_5v_voltage_entries[j].setText(str(self.five_voltage[j]))
            self.board_5v_current_entries[j].setText(str(self.five_current[j]))
            self.board_cond_voltage_entries[j].setText(str(self.cond_voltage[j]))
            self.board_cond_current_entries[j].setText(str(self.cond_current[j]))

    # acquires the channel being measured
    def get_blade_channel(self):
        # determine which blade data is to be plotted for
        channels={"Channel 1": 0,"Channel 2": 1,"Channel 3": 2,"Channel 4": 3,"Channel 5": 4,"Channel 6": 5}
        channel=channels[self.blade_channel_selector.currentText()]
        return channel

    def get_board_channel(self):
        # determine which blade data is to be plotted for
        channels={"Channel 1": 0,"Channel 2": 1,"Channel 3": 2,"Channel 4": 3,"Channel 5": 4,"Channel 6": 5}
        channel=channels[self.board_channel_selector.currentText()]
        return channel

    # instantly changes what's being displayed on the main plot, depending on the user's selection
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

        if type=="Voltage":
            self.blade_plot_data.set_ydata(self.blade_voltage_plot[channel])
        elif type=="Current":
            self.blade_plot_data.set_ydata(self.blade_current_plot[channel])
        else:
            self.blade_plot_data.set_ydata(self.blade_temperature_plot[channel])
        self.blade_plot_canvas.draw()
        self.blade_plot_canvas.flush_events()

    def change_board_plot(self):
        channel=self.get_board_channel()
        type=self.board_measurement_selector.currentText()

        # update labels for the board plot
        self.board_plot_axes.set_title(self.board_channel_selector.currentText() + ' Board ' + type)
        if type=="5V Voltage":
            self.board_plot_axes.set_ylabel('5V Voltage (V)')
        elif type=="5V Current":
            self.board_plot_axes.set_ylabel('5V Current (A)')
        elif type=="Conditioned Voltage":
            self.board_plot_axes.set_ylabel('Conditioned Voltage (V)')
        else:
            self.board_plot_axes.set_ylabel('Conditioned Current (A)')




        if type=="5V Voltage":
            self.board_plot_data.set_ydata(self.board_5v_voltage_plot[channel])
        elif type=="5V Current":
            self.board_plot_data.set_ydata(self.board_5v_current_plot[channel])
        elif type=="Conditioned Voltage":
            self.board_plot_data.set_ydata(self.board_cond_voltage_plot[channel])
        else:
            self.board_plot_data.set_ydata(self.board_cond_current_plot[channel])
        self.board_plot_canvas.draw()
        self.board_plot_canvas.flush_events()



    # called by the timer to update the main plot with new data
    def update_blade_plot(self):
        channel=self.get_blade_channel()
        type=self.blade_measurement_selector.currentText()

        # rotate plot lists
        for i in range(len(self.blade_voltage_plot)):
            self.blade_voltage_plot[i]=[self.voltage[i]]+self.blade_voltage_plot[i][:-1]
            self.blade_current_plot[i]=[self.current[i]]+self.blade_current_plot[i][:-1]
            self.blade_temperature_plot[i]=[self.temperature[i]]+self.blade_temperature_plot[i][:-1]

        if type=="Voltage":
            self.blade_plot_data.set_ydata(self.blade_voltage_plot[channel])
        elif type=="Current":
            self.blade_plot_data.set_ydata(self.blade_current_plot[channel])
        else:
            self.blade_plot_data.set_ydata(self.blade_temperature_plot[channel])
        self.blade_plot_canvas.draw()
        self.blade_plot_canvas.flush_events()

    def update_board_plot(self):
        channel=self.get_board_channel()
        type=self.board_measurement_selector.currentText()

        # rotate plot lists
        for i in range(len(self.board_5v_voltage_plot)):
            self.board_5v_voltage_plot[i]=[self.five_voltage[i]]+self.board_5v_voltage_plot[i][:-1]
            self.board_5v_current_plot[i]=[self.five_current[i]]+self.board_5v_current_plot[i][:-1]
            self.board_cond_voltage_plot[i]=[self.cond_voltage[i]]+self.board_cond_voltage_plot[i][:-1]
            self.board_cond_current_plot[i]=[self.cond_current[i]]+self.board_cond_current_plot[i][:-1]

        if type=="5V Voltage":
            self.board_plot_data.set_ydata(self.board_5v_voltage_plot[channel])
        elif type=="5V Current":
            self.board_plot_data.set_ydata(self.board_5v_current_plot[channel])
        elif type=="Conditioned Voltage":
            self.board_plot_data.set_ydata(self.board_cond_voltage_plot[channel])
        else:
            self.board_plot_data.set_ydata(self.board_cond_current_plot[channel])
        self.board_plot_canvas.draw()
        self.board_plot_canvas.flush_events()

    def assorted_update(self):
        self.get_data(True)
        self.update_blade_table()
        self.update_board_table()
        self.update_blade_plot()
        self.update_board_plot()
        self.save_txt()

    def initialize_data(self):
        self.blade_voltage_plot=[[500]*50]*6
        self.blade_current_plot=[[500]*50]*6
        self.blade_temperature_plot=[[500]*50]*6

        self.board_5v_voltage_plot=[[500]*50]*6
        self.board_5v_current_plot=[[500]*50]*6
        self.board_cond_voltage_plot=[[500]*50]*6
        self.board_cond_current_plot=[[500]*50]*6

        # keeps track of blade power statuses
        self.blade_power=[False]*6

    def run(self):
        self.timer = QTimer(self)
        self.timer.setSingleShot(False)
        self.timer.timeout.connect(self.assorted_update)
        self.timer.start(1000)

if __name__=="__main__":
    try:
        # create pyqt5 app
        App = QApplication(sys.argv)
        # create the instance of our Window
        window = Window()

        window.run()

        # start the app
        sys.exit(App.exec())

    except KeyboardInterrupt:
        stored_exception=sys.exc_info()
    except Exception as e:
        print (type(e),e)
