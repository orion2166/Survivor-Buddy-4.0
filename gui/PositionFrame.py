#!/usr/bin/env python3
"""
Contains elements which control the arduino/arm hardware. Also contains the graphical representation of the arm
"""

import tkinter as tk
import tkinter.ttk as ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib as mpl
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
from threading import Thread
from datetime import datetime
from os.path import expanduser
import time
import queue
from .tkvlc import Player
from .ControlButtons import ControlButtons

class PositionUpdater(Thread):
    '''Updates UI elements based on arm position'''

    def __init__(self, dev, _pitch_control, _yaw_control, _roll_control, _yaw_queue, _pitch_queue, _roll_queue, _notifications, **kwargs):
        '''
        Constructor for PositionUpdater
        
        :param dev: The SerialArmController
        :type dev: SerialArmController
        :param _pitch_control: The pitch LabelScaleSpinbox
        :type _pitch_control: LabelScaleSpinbox
        :param _yaw_control: The yaw LabelScaleSpinbox
        :type _yaw_control: LabelScaleSpinbox
        :param _roll_control: The roll LabelScaleSpinbox
        :type _roll_control: LabelScaleSpinbox
        :param _yaw_queue: A queue that stores yaw values
        :type _yaw_queue: queue
        :param _pitch_queue: A queue that stores pitch values
        :type _pitch_queue: queue
        :param _roll_queue: A queue that stores roll values
        :type _roll_queue: queue
        :param _notifications: The NotificationsFrame
        :type _notifications: NotificationsFrame
        '''

        super().__init__(**kwargs)
        self.serial_arm_controller = dev
        self.pitch_control = _pitch_control
        self.yaw_control = _yaw_control
        self.roll_control = _roll_control
        self.yaw_queue = _yaw_queue
        self.pitch_queue = _pitch_queue
        self.roll_queue = _roll_queue
        self.notifications = _notifications


    def run(self):
        '''
        Continually checks for changes to arm position, then updates the UI based on these changes, checks for changes every 0.1 seconds.
        Runs as a thread separately from rest of UI, uses queue to update render and directly updates sliders and spinboxes.
        '''

        yaw = 0
        pitch = 0
        roll = 0
        while True:
            if self.serial_arm_controller.is_connected: #If else to allow testing of GUI without connected arm
                try:
                    self.serial_arm_controller.update_position()
                    pitch = self.serial_arm_controller.position.pitch
                    yaw = self.serial_arm_controller.position.yaw
                    roll = self.serial_arm_controller.position.roll
                    self.pitch_control.slider.set(pitch)
                    self.pitch_control.spinbox.set(pitch)
                    self.yaw_control.slider.set(yaw)
                    self.yaw_control.spinbox.set(yaw)
                    self.roll_control.slider.set(roll)
                    self.roll_control.spinbox.set(roll)
                except: # disconnected
                    self.notifications.append_line("WARNING: DEVICE DISCONNECTED")
                    self.serial_arm_controller.close()
            else:
                pitch = self.pitch_control.spinbox.get()
                yaw = self.yaw_control.spinbox.get()
                roll = self.roll_control.spinbox.get()
            if (self.yaw_queue.empty()):   #Only add to queue if queue is empty, otherwise will fill with values, getting out of sync with render and memory leak
                self.yaw_queue.put(yaw)
            if (self.pitch_queue.empty()):
                self.pitch_queue.put(pitch)
            if (self.roll_queue.empty()):
                self.roll_queue.put(roll)
            time.sleep(0.1)


class LabelScaleSpinbox(tk.Frame):
    '''
    A custom class to combine Tk Scale and Spinbox and keep them in sync

    '''

    def __init__(
        self, 
        master, 
        text="", 
        from_=0, 
        to=10, 
        axis=0, 
        dev=None, 
        up=False, 
        down=False, 
        left=False, 
        right=False, 
        top_frame=None, 
        middle_frame=None, 
        bottom_frame=None, 
        root=None, 
        app_master=None,
        **kwargs
    ):
        '''
        Constructor for LabelScaleSpinbox
        
        :param master: The Tk parent widget
        :type master: Tk
        :param text: The text to display next to the control
        :type text: String
        :param from_: The minimum valid value
        :type from_: int
        :param to: The maximum valid value
        :type to: int
        :param axis: The axis that this LabelScaleSpinbox controls, range: [0,2]; 0 means pitch, 1 means yaw, and 2 means roll
        :type axis:  int
        :param dev: The SerialArmController
        :type dev: SerialArmController
        :param up: Tells us if we need to create the "move up" button on GUI
        :type up: boolean
        :param down: Tells us if we need to create the "move down" button on GUI
        :type down: boolean
        :param left: Tells us if we need to create the "move left" button on GUI
        :type left: boolean
        :param right: Tells us if we need to create the "move right" button on GUI
        :type right: boolean
        :param top_frame: Frame passed in to denote placement of buttons around the video frame. Top frame will be used to place the "move up" button
        :type top_frame: Frame (from Tkinter)
        :param middle_frame: Frame passed in to denote placement of buttons around the video frame. Middle frame will be used to place the "move left" button, "move right" button, and the video frame itself
        :type middle_frame: Frame (from Tkinter)
        :param bottom_frame: Frame passed in to denote placement of buttons around the video frame. Bottom frame will be used to place the "move down" button
        :type bottom_frame: Frame (from Tkinter)
        :param root: The highest level tkinter frame
        :type root: Tk
        :param app_master: The application.py's master variable
        :type app_master: Tk
        '''

        super().__init__(master, **kwargs)
        
        self.app_frame = app_master

        self.min = from_
        self.max = to
        self.axis = axis
        self.serial_arm_controller = dev
        
        if text:
            self.label = ttk.Label(self, text=text)
            self.label.pack(side="left")
        
        self.from_label = ttk.Label(self, text=str(from_))
        self.from_label.pack(side="left")
        
        self.slider = ttk.Scale(self, from_=from_, to=to, orient="horizontal", length=200)
        self.slider.bind("<ButtonRelease-1>", self.sliderUpdate)
        self.slider.pack(side="left")
        
        self.to_label = ttk.Label(self, text=str(to))
        self.to_label.pack(side="left")  
        
        spinbox_vcmd = self.register(self.validate_spinbox)
        spinbox_ivcmd = self.register(self.invalid_spinbox)
        self.spinbox = ttk.Spinbox(
            self,
            from_=from_,
            to=to,
            width=4, 
            command=self.set_slider,
            validate="focusout", 
            validatecommand=(spinbox_vcmd, "%P"),
            invalidcommand=(spinbox_ivcmd,),
            state=tk.DISABLED
        )
        
        self.current_value = self.slider.get()
        self.spinbox.set(self.current_value)
        self.spinbox.pack(side="right")

        self.root = root

        if up:
            self.up_button = ttk.Button(top_frame,
                                   text="Move up", command=self.incrementUp)
            self.up_button.pack(side="top")

        if left and right:
            self.left_button = ttk.Button(middle_frame,
                                          text="Move left", command=self.decrementLeft)
            self.left_button.pack(side="left")
            self.app_frame.player = Player(middle_frame, self.app_frame.video_url)#tk.Frame(middle_frame, height=800, width=400, background='cyan')
            self.app_frame.player.pack(side='left', expand=True, pady=5)
            
            self.right_button = ttk.Button(middle_frame,
                                           text="Move right", command=self.incrementRight)
            self.right_button.pack(side="left")
        if down:
            self.down_button = ttk.Button(bottom_frame,
                                        text="Move down", command=self.decrementDown)
            self.down_button.pack(side="top")


    def sliderUpdate(self, val):
        '''
        Sends command to arm based on slider value, sets spinbox based on slider
        
        :param val: The value passed to this function when the slider is released
        :type val: int
        '''
        newVal = int(self.slider.get())
        self.spinbox.set(newVal)    #Update spinbox value
        self.current_value = newVal
        self.send_command()

    def incrementUp(self):
        '''
        Functionality for the "move up" button on the GUI, currently increments by 5 units

        '''

        newVal = int(self.spinbox.get())
        newVal = newVal + 5
        if newVal >= 90:
            self.serial_arm_controller.notifications.append_line("Error: Can't Move Up Any Farther")
        else:
            self.spinbox.set(newVal)
            self.current_value = newVal
            self.set_slider()
            self.send_command()

    def incrementRight(self):
        '''
        Functionality for the "move right" button on the GUI, currently increments by 20 units

        '''
        newVal = int(self.spinbox.get())
        newVal = newVal + 20
        if newVal >= 90:
            self.serial_arm_controller.notifications.append_line("Error: Can't Move Right Any Farther")
        else:
            self.spinbox.set(newVal)
            self.current_value = newVal
            self.set_slider()
            self.send_command()


    def decrementLeft(self):
        '''
        Functionality for the "move left" button on the GUI, currently decrements by 20 units

        '''
        newVal = int(self.spinbox.get())
        newVal = newVal - 20
        if newVal <= -90:
            self.serial_arm_controller.notifications.append_line("Error: Can't Move Left Any Farther")
        else:
            self.spinbox.set(newVal)
            self.current_value = newVal
            self.set_slider()
            self.send_command()

    def decrementDown(self):
        '''
        Functionality for the "move down" button on the GUI, currently decrements by 20 units

        '''
        newVal = int(self.spinbox.get())
        newVal = newVal - 5
        if newVal <= 0:
            self.serial_arm_controller.notifications.append_line("Error: Can't Move Down Any Farther")
        else:
            self.spinbox.set(newVal)
            self.current_value = newVal
            self.set_slider()
            self.send_command()


    def validate_spinbox(self, val):
        '''
        Check that spinbox and slider are within valid range of values
        
        :param val: The value from the spinbox
        :type val: int
        '''

        try:
            print(type(val))
            ival = int(val)
            if ival < self.min or ival > self.max:
                self.spinbox.set(str(round(self.current_value)))
                return False
            else:
                # input is good. Set Slider value
                self.slider.set(ival)
                return True
        except:
            self.spinbox.set(str(round(self.current_value)))
            return False
        

    def invalid_spinbox(self):
        '''
        Function that runs when the spinbox has an invalid value
        '''

        print("Error: Position input must be a number between {} and {}".format(self.min, self.max))
    

    def set_slider(self):
        '''
        Set slider position based on spinbox value, send command to arm
        '''

        try:
            val = int(self.spinbox.get())
        except:
            print("Error: Input must be a number")
            return
        self.slider.set(val)
        self.current_value = val
        self.send_command()
    

    def send_command(self):
        '''
        Sends a new position to the arm based on changed axis
        '''

        if self.serial_arm_controller.is_connected:
            if self.axis == 0:  #Pitch
                self.serial_arm_controller.set_pitch(self.current_value)
                #print ("curr val:", self.current_value)
            elif self.axis == 1:    #Yaw
                self.serial_arm_controller.set_yaw(self.current_value)
            elif self.axis == 2:    #Roll
                self.serial_arm_controller.set_roll(self.current_value)  
        

class RenderDiagram(tk.Frame): 
    '''
    Displays a basic render of arm, helps to show position when arm can not be seen by user
    '''

    def __init__(self, master, dev=None, **kwargs):
        '''
        Constructor for RenderDiagram
        
        :param master: The Tk parent widget
        :param dev: The SerialArmController
        '''

        super().__init__(master, **kwargs)

        self.serial_arm_controller = dev

        # Disable plot toolbar
        mpl.rcParams['toolbar'] = 'None'

        # Set up 3d plot, define size
        self.fig = plt.figure(figsize=(4.5,4.5))
        self.ax = self.fig.gca(projection='3d')

        self.draw_axes() #Split into separate function, as axes must be redrawn each frame

        self.render_canvas = FigureCanvasTkAgg(self.fig, master)
        self.render_canvas.get_tk_widget().pack()

        self.yawD = 0   #Degree values for yaw, pitch and roll
        self.pitchD = 0
        self.rollD = 0
    

    def draw_axes(self):
        '''
        Clear units from axes, display arm base, set axis limits
        '''

        # Remove unneccesary information from plot
        self.ax.set_xticklabels([])
        self.ax.set_yticklabels([])
        self.ax.set_zticklabels([])

        # Draw x, y and z axes to make plot easier to read, set plot size
        # self.ax.quiver(-2, 0, 0, 4, 0, 0, length=1.0, arrow_length_ratio=0, color = '#cf685d') #red, left-right
        # self.ax.quiver(0, -2, 0, 0, 4, 0, length=1.0, arrow_length_ratio=0, color = '#5d5fcf') #blue, front-back
        # self.ax.quiver(0, 0, 0, 0, 0, 4, length=1.0, arrow_length_ratio=0, color = '#6ad15e') #green, height

        self.ax.quiver(-1, 1.5, 0, 0, -3, 0, length=1.0, arrow_length_ratio=0, color = '#727985')   #Draw basic diagram of arm base to improve readability
        self.ax.quiver(1, 1.5, 0, 0, -3, 0, length=1.0, arrow_length_ratio=0, color = '#727985')
        self.ax.quiver(-0.4, 1.5, 0, 0, -1, 0, length=1.0, arrow_length_ratio=0, color = '#727985')
        self.ax.quiver(0.4, 1.5, 0, 0, -1, 0, length=1.0, arrow_length_ratio=0, color = '#727985')
        self.ax.quiver(1, 1.5, 0, -0.6, 0 , 0, length=1.0, arrow_length_ratio=0, color = '#727985')
        self.ax.quiver(-1, 1.5, 0, 0.6, 0 , 0, length=1.0, arrow_length_ratio=0, color = '#727985')
        self.ax.quiver(0.4, 0.5, 0, -0.8, 0 , 0, length=1.0, arrow_length_ratio=0, color = '#727985')
        self.ax.quiver(1, -1.5, 0, -2, 0 , 0, length=1.0, arrow_length_ratio=0, color = '#727985')

        self.ax.set_xlim(left=-2, right=2, emit=True, auto=False)
        self.ax.set_ylim(bottom=-2, top=2, emit=True, auto=False)
        self.ax.set_zlim(bottom=0, top=4, emit=True, auto=False)
        self.ax.set_xlabel('FRONT')


    def update_render(self, master, new_yaw, new_pitch, new_roll):
        '''
        Update display of render based on new arm position
        
        :param master: The Tk parent widget
        :type master: Tk
        :param new_yaw: The new yaw value
        :type new_yaw: int
        :param new_pitch: The new pitch value
        :type new_pitch: int
        :param new_roll: The new roll value
        :type new_roll: int
        '''

        self.ax.clear() #clear old data
        self.draw_axes()    #redraw axes
        yaw = -float(new_yaw) * np.pi / 180  #Convert angles to radians
        pitch = float(new_pitch) * np.pi / 180
        roll = float(new_roll) * np.pi / 180
        self.yawD = new_yaw
        self.pitchD = new_pitch
        self.rollD = new_roll

        self.ax.quiver(0.2, 1, 0, 0, -np.cos(pitch), np.sin(pitch), length=2, arrow_length_ratio=0, color = '#a83e32') #Arm wireframe
        self.ax.quiver(-0.2, 1, 0, 0, -np.cos(pitch), np.sin(pitch), length=2, arrow_length_ratio=0, color = '#a83e32')
        self.ax.quiver(0.2, 1, 0, -0.4, 0, 0, length=1.0, arrow_length_ratio=0, color = '#a83e32')
        self.ax.quiver(0.2, -np.cos(pitch)*2 + 1, np.sin(pitch)*2, -0.4, 0, 0, length=1.0, arrow_length_ratio=0, color = '#a83e32')

        self.ax.quiver( #Vector of phone yaw direction
            0, 
            -np.cos(pitch)*1.75 + 1, 
            np.sin(pitch)*1.75, 
            - np.sin(yaw),
            np.sin(pitch + np.pi) * np.cos(yaw),
            np.cos(pitch + np.pi) * np.cos(yaw), 
            length=2.0, arrow_length_ratio=0.25, color = '#32a852') 

        self.ax.quiver(
            0.5 * np.cos(roll) + 0.75 * np.sin(roll), 
            -2.5 * np.cos(pitch)  + 1.25* np.sin(roll) * np.sin(roll) * np.cos(pitch)   + 1, 
            -0.5 * np.sin(roll) * np.sin(pitch) + (np.sin(pitch)*0.75) * np.cos(roll) + np.sin(pitch)*1.75, 
            -1 * np.cos(roll), 
            -1 * np.sin(roll)* np.sin(roll) * np.cos(pitch), 
            1 * np.sin(roll) * np.sin(pitch),  
            length=1.0, arrow_length_ratio=0, color = '#3e48d6'
            )

        self.ax.quiver(
            0.5 * np.cos(roll) + 0.75 * np.sin(roll), 
            -2.5 * np.cos(pitch)  + 1.25* np.sin(roll) * np.sin(roll) * np.cos(pitch)   + 1, 
            -0.5 * np.sin(roll) * np.sin(pitch) + (np.sin(pitch)*0.75) * np.cos(roll) + np.sin(pitch)*1.75, 
            -1.5 * np.sin(roll), 
            1.5 * np.cos(roll) * np.cos(roll) * np.cos(pitch), 
            -1.5 * np.cos(roll) * np.sin(pitch),  
            length=1.0, arrow_length_ratio=0, color = '#3e48d6'
            )

        self.ax.quiver(
            -0.5 * np.cos(roll) + 0.75* -np.sin(roll), 
            -1 * np.cos(pitch) - 1.25* np.sin(roll) * np.sin(roll) * np.cos(pitch)  + 1, 
            0.5 * np.sin(roll) * np.sin(pitch) + (np.sin(pitch)*0.75) * -np.cos(roll) + np.sin(pitch)*1.75, 
            1 * np.cos(roll), 
            1 * np.sin(roll)* np.sin(roll) * np.cos(pitch), 
            -1 * np.sin(roll) * np.sin(pitch), 
            length=1.0, arrow_length_ratio=0, color = '#3e48d6'
            )

        self.ax.quiver(
            -0.5 * np.cos(roll) + 0.75* -np.sin(roll), 
            -1 * np.cos(pitch) - 1.25* np.sin(roll) * np.sin(roll) * np.cos(pitch)  + 1, 
            0.5 * np.sin(roll) * np.sin(pitch) + (np.sin(pitch)*0.75) * -np.cos(roll) + np.sin(pitch)*1.75, 
            1.5 * np.sin(roll), 
            -1.5 * np.cos(roll)* np.cos(roll) * np.cos(pitch), 
            1.5 * np.cos(roll) * np.sin(pitch), 
            length=1.0, arrow_length_ratio=0, color = '#3e48d6'
            )
        
        self.ax.quiver( #Arrow pointing to top of phone
            0, 
            -np.cos(pitch)*1.75 + 1, 
            np.sin(pitch)*1.75,
            0.75 * np.sin(roll), 
            -0.75 * np.cos(roll) * np.cos(pitch), 
            0.75 * np.cos(roll) * np.sin(pitch), 
            length=1.0, arrow_length_ratio=0.5, color = '#0917de'
            )

        self.render_canvas.draw()


class PositionFrame(tk.Frame):
    '''Creates the Render and Control Sliders in the GUI'''

    def __init__(self, master, arm_controller, _logFile, top_frame, middle_frame, bottom_frame, root, notifications_frame, **kwargs):
        '''
        Constructor for PositionFrame
        
        :param master: The Tk parent widget
        :type master: Tk
        :param arm_controller: The SerialArmController
        :type arm_controller: SerialArmController
        :param _logFile: The output log file handle
        :type _logFile: file object
        :param top_frame: Frame to be later used in LabelScaleSpinBox
        :type top_frame: Frame (from Tkinter)
        :param middle_frame: Frame to be later used in LabelScaleSpinBox
        :type middle_frame: Frame (from Tkinter)
        :param bottom_frame: Frame to be later used in LabelScaleSpinBox
        :type bottom_frame: Frame (from Tkinter)
        :param root: The outmost Tk application (called root inside the main function in Application.py)
        :type root: Tk
        :param notifications_frame: The NotificationsFrame
        :type notifications_frame: NotificationsFrame
        '''

        super().__init__(master, **kwargs)
        self._master = master
        self.notifications_frame = notifications_frame
        self.serial_arm_controller = arm_controller
        self.logFile = _logFile
        self.top_frame = top_frame
        self.middle_frame = middle_frame
        self.bottom_frame = bottom_frame

        self.root = root

        self.render_frame = tk.Frame(self)
        self.render_frame.pack(side="top")
        self.create_render(self.render_frame)
        self._master.control_buttons =ControlButtons(self, self.serial_arm_controller, self.notifications_frame)
        self._master.control_buttons.pack(side="top", pady=20)
        self.control_frame = tk.Frame(self)
        self.control_frame.pack(side="top")
        self.create_controls(self.control_frame, self._master)

        # self._master.text_box = tk.Text(self.control_frame, width=20, height=5)
        # self._master.send_button = tk.Button(self.control_frame, text="Send Text", height=5, command=self._master.send_text)
        # self.notifications_frame.pack(side="bottom")
        # self._master.send_button.pack(side="right")


        

        self.yaw_queue = queue.LifoQueue()
        self.pitch_queue = queue.LifoQueue()
        self.roll_queue = queue.LifoQueue()

        self.create_updater()
        self.frame_master = self.render_frame    #s.t. master does not have to be passed to process queue
        self.master.after(100, self.process_queue)




    def create_render(self, master):    
        '''
        Initializes render of arm
        
        :param master: The Tk parent widget
        :type master: Tk
        '''

        self.pos_render = RenderDiagram(
            master, dev=self.serial_arm_controller
        )
        self.pos_render.pack()
    

    def create_controls(self, master, app_master):
        '''
        Creates LabelScaleSpinbox controls
        
        :param master: The Tk parent widget
        :type master: Tk
        '''

        self.pitch_control = LabelScaleSpinbox(
            master, text="Pitch: ", from_=0, to=90, axis=0, dev=self.serial_arm_controller, up=True, down=True, left=False, right=False, top_frame=self.top_frame, middle_frame=self.middle_frame, bottom_frame=self.bottom_frame, root=self.root, app_master=app_master)
        self.pitch_control.pack()
        
        self.yaw_control = LabelScaleSpinbox(
            master, text="Yaw: ", from_=-90, to=90, axis=1, dev=self.serial_arm_controller, up=False, down=False, left=True, right = True, top_frame=self.top_frame, middle_frame=self.middle_frame, bottom_frame=self.bottom_frame, root=self.root, app_master=app_master)
        self.yaw_control.pack()
        
        self.roll_control = LabelScaleSpinbox(
            master, text="Roll: ", from_=0, to=90, axis=2, dev=self.serial_arm_controller, up=False, down=False, left=False, right=False, top_frame=self.top_frame, middle_frame=self.middle_frame, bottom_frame=self.bottom_frame, root=self.root, app_master=app_master)
        self.roll_control.pack()


    def create_updater(self):
        '''
        Starts updater function to update GUI based on current position

        '''

        self.update_thread = PositionUpdater(
            self.serial_arm_controller,
            self.pitch_control,
            self.yaw_control,
            self.roll_control,
            self.yaw_queue,
            self.pitch_queue,
            self.roll_queue,
            self._master.notifications_frame
        )
        self.update_thread.setDaemon(True)
        self.update_thread.start()


    def process_queue(self):
        '''
        Processes queue of position updates

        Uses this queue data to print new position to log file, and to update render position
        '''

        if(not (self.yaw_queue.empty() or self.pitch_queue.empty() or self.roll_queue.empty())):
            newYaw = self.yaw_queue.get(0)
            newPitch = self.pitch_queue.get(0)
            newRoll = self.roll_queue.get(0)
            if (newYaw != self.pos_render.yawD or newPitch != self.pos_render.pitchD or newRoll != self.pos_render.rollD):
                now = datetime.now()
                timestamp = now.strftime("%H:%M:%S")
                self.logFile.write(str(timestamp) + " - Position: P: " + str(newPitch) + " Y: " + str(newYaw) + " R: " + str(newRoll) + "\n")
            self.pos_render.update_render(self.frame_master, newYaw, newPitch, newRoll)
        self.master.after(50, self.process_queue)
