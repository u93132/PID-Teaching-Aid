# -*- coding: utf-8 -*-
import os, sys, signal, tempfile
from dataclasses import dataclass
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog

from functions import *
from boxBase import *
from simulation import simulate, analyze
from plotPanel import PlotPanel
from animPanel import AnimPanel

VERSION = '2.0.0'


@dataclass(slots=True)
class Setting:
    # User-adjustable options, restored on the next launch
    kp: float = 20.0
    ki: float = 0.0
    kd: float = 0.0
    watermark: int = 1


# Define the application class
class PIDTeachingAid(tk.Tk):
    def __init__(self, *args, **kwargs):

        ########################################################################
        ############################## Initialize ##############################
        ########################################################################

        # Initialize tk
        tk.Tk.__init__(self, *args, **kwargs)
        self.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.title('PID Control Teaching Tool')
        # Fonts from Windows OS
        myFont = tkfont.Font(family=FindFont(), size=9)
        self.option_add('*font', myFont)
        # Load Icons
        try:
            self.iconbitmap(bitmap=str(resource_path('image0/Icon.ico')))
        except tk.TclError:
            pass
        # Locate to the middle
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        # Dimension of the GUI
        w = 1280
        h = 720
        x = (ws / 2) - (w / 2)
        y = (hs / 2) - (h / 2)
        self.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        self.resizable(width=False, height=False)
        self.bind('<Control-Key-F2>', self.ToggleWatermark)
        # ttk styles
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Small.TButton', padding=0, width=2)
        # Plant parameters
        self.m, self.c, self.k = 1.0, 0.5, 2.0
        # Simulation setup
        self.t_total = 16.0
        self.dt      = 0.02
        # Animation state
        self.is_ready     = False
        self.anim_running = False
        self.is_paused    = False
        self.current_step = 0
        self.res = None   # latest SimResult
        self.met = None   # latest Metrics
        self.sample_rate = 4   # export: one frame per 4 steps = 12.5 FPS
        # Settings
        self.settingfile = Path(tempfile.gettempdir()) / 'PIDTeachingAid.txt'
        self.data = self.LoadSetting()
        self.show_watermark = bool(self.data.watermark)

        ########################################################################
        ####################### GUI objects : Control Panel ####################
        ########################################################################

        self.controlframe = ttk.Frame(self, padding='5')
        self.controlframe.pack(side='left', fill='y')
        # Plant parameters display
        ttk.Label(self.controlframe, text='Plant Parameters',
                  font=('Arial', 14, 'bold')).pack(pady=5)
        sys_text = (f'Mass (m): {self.m:.2f}\n'
                    f'Damping (c): {self.c:.2f}\n'
                    f'Stiffness (k): {self.k:.2f}')
        self.SysLabel = ttk.Label(self.controlframe, text=sys_text,
                                  font=('Courier', 11))
        self.SysLabel.pack(pady=5)
        ttk.Separator(self.controlframe, orient='horizontal')\
           .pack(fill='x', pady=15)
        # PID parameters display and sliders
        ttk.Label(self.controlframe, text='PID Parameters',
                  font=('Arial', 14, 'bold')).pack(pady=5)
        self.InfoLabel = ttk.Label(self.controlframe, text='',
                                   font=('Courier', 11))
        self.InfoLabel.pack(pady=10)
        self.KpSlider = SliderBox(self.controlframe, 'Kp (Proportional)',
                                  0, 100, self.data.kp,
                                  self.HandleSliderChange)
        self.KiSlider = SliderBox(self.controlframe, 'Ki (Integral)',
                                  0, 50, self.data.ki,
                                  self.HandleSliderChange)
        self.KdSlider = SliderBox(self.controlframe, 'Kd (Derivative)',
                                  0, 20, self.data.kd,
                                  self.HandleSliderChange)
        self.sliders = [self.KpSlider, self.KiSlider, self.KdSlider]
        guide_text = ('Tuning Guide:\n'
                      '1. Increase Kp for speed\n'
                      '2. Increase Kd to stop oscillation\n'
                      '3. Increase Ki to fix offset')
        ttk.Label(self.controlframe, text=guide_text,
                  foreground='#666').pack(anchor='w', pady=5)
        ttk.Separator(self.controlframe, orient='horizontal')\
           .pack(fill='x', pady=20)

        ########################################################################
        ###################### GUI objects : Animation Control #################
        ########################################################################

        ttk.Label(self.controlframe, text='Animation Control',
                  font=('Arial', 12, 'bold')).pack(pady=5)
        self.btnframe = ttk.Frame(self.controlframe)
        self.btnframe.pack(fill='x', pady=5)
        self.PlayButton   = ttk.Button(self.btnframe, text='Play', width=6,
                                       command=self.PlayAnimation)
        self.PlayButton   .pack(side='left', expand=True, fill='x', padx=1)
        self.PauseButton  = ttk.Button(self.btnframe, text='Pause', width=6,
                                       command=self.PauseAnimation)
        self.PauseButton  .pack(side='left', expand=True, fill='x', padx=1)
        self.StopButton   = ttk.Button(self.btnframe, text='Stop', width=6,
                                       command=self.StopAnimation)
        self.StopButton   .pack(side='left', expand=True, fill='x', padx=1)
        self.ExportButton = ttk.Button(self.btnframe, text='Export', width=6,
                                       command=self.ExportAnimation)
        self.ExportButton .pack(side='left', expand=True, fill='x', padx=1)
        ToolTip(self.PlayButton,   'Play the response animation')
        ToolTip(self.PauseButton,  'Pause the animation')
        ToolTip(self.StopButton,   'Stop and rewind the animation')
        ToolTip(self.ExportButton, 'Export the animation as a GIF\n'
                                   '(Ctrl+F2 toggles the watermark)')
        # Spring-mass animation figure
        self.anim = AnimPanel(self.controlframe)

        ########################################################################
        ########################## GUI objects : Charts ########################
        ########################################################################

        self.plot = PlotPanel(self)

        # First simulation with the restored gains
        self.is_ready = True
        self.UpdatePlot()
        self.AnimState(0)

    ############################################################################
    ############################## Class Functions #############################
    ############################################################################

    def on_closing(self):
        self.is_ready = False
        self.anim_running = False
        self.WriteSetting()
        # The figures live on the embedded canvases (no pyplot
        # registry), so they die with the window
        # The packed exe needs a hard exit, plain destroy() in dev
        if getattr(sys, 'frozen', False):
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            self.destroy()

    def AnimState(self, i):
        # One function decides every button's enable/disable:
        # i = 0: idle, 1: playing, 2: paused, 3: exporting
        match i:
            case 0:
                self.PlayButton  .config(state='normal')
                self.PauseButton .config(state='disabled')
                self.StopButton  .config(state='disabled')
                self.ExportButton.config(state='normal')
                for s in self.sliders:
                    s.SetState(True)
            case 1:
                self.PlayButton  .config(state='disabled')
                self.PauseButton .config(state='normal')
                self.StopButton  .config(state='normal')
                self.ExportButton.config(state='disabled')
            case 2:
                self.PlayButton  .config(state='normal')
                self.PauseButton .config(state='disabled')
                self.StopButton  .config(state='normal')
                self.ExportButton.config(state='disabled')
            case 3:
                self.PlayButton  .config(state='disabled')
                self.PauseButton .config(state='disabled')
                self.StopButton  .config(state='disabled')
                self.ExportButton.config(state='disabled')
                for s in self.sliders:
                    s.SetState(False)

    def HandleSliderChange(self):
        # Any gain change stops the playback and redraws the charts
        if not self.is_ready:
            return
        self.StopAnimation()
        self.UpdatePlot()

    def UpdatePlot(self):
        kp = self.KpSlider.get()
        ki = self.KiSlider.get()
        kd = self.KdSlider.get()
        self.InfoLabel.config(text=(f'Kp: {kp:6.2f}\n'
                                    f'Ki: {ki:6.2f}\n'
                                    f'Kd: {kd:6.2f}'))
        self.res = simulate(kp, ki, kd, m=self.m, c=self.c, k=self.k,
                            t_total=self.t_total, dt=self.dt)
        self.met = analyze(self.res.t, self.res.y)
        self.plot.UpdatePlot(self.res, self.met)
        self.anim.SetParamText(self.m, self.c, self.k, kp, ki, kd)

    ############################################################################
    ############################# Animation Control ############################
    ############################################################################

    def PlayAnimation(self):
        # Start from the top, or resume from a pause
        if not self.anim_running:
            self.anim_running = True
            self.is_paused    = False
            self.current_step = 0
        elif self.is_paused:
            self.is_paused = False
        else:
            return
        self.anim.ShowHand(True)
        self.AnimState(1)
        self.RunAnimationLoop()

    def PauseAnimation(self):
        if self.anim_running:
            self.is_paused = True
            self.AnimState(2)

    def StopAnimation(self):
        self.anim_running = False
        self.is_paused    = False
        self.current_step = 0
        self.anim.ShowHand(False)
        self.anim.UpdateVisual(0.0, 0.0, 0.0)
        self.plot.HideCursor()
        self.AnimState(0)

    def RunAnimationLoop(self):
        # Core playback loop on the tk event queue
        if not self.anim_running or self.is_paused or self.res is None:
            return
        if self.current_step < len(self.res.y):
            i = self.current_step
            self.anim.UpdateVisual(self.res.y[i], self.res.t[i],
                                   self.res.u[i])
            self.plot.SetCursor(self.res.t[i], self.res.y[i],
                                self.res.u[i])
            # Playback speed: two steps per 20 ms tick
            self.current_step += 2
            self.after(20, self.RunAnimationLoop)
        else:
            # The run finished on its own; the hand stays until Stop
            self.anim_running = False
            self.AnimState(0)

    def ToggleWatermark(self, event=None):
        self.show_watermark = not self.show_watermark

    def ExportFrameHook(self, pos, curr_t, curr_u):
        # Called between exported frames: keep the chart cursor moving
        # and the window responsive
        self.plot.SetCursor(curr_t, pos, curr_u)
        self.update()

    def ExportAnimation(self):
        if self.res is None:
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension='.gif',
            initialfile='PID',
            filetypes=[('GIF Animation', '*.gif')])
        if not file_path:
            return
        self.StopAnimation()
        self.AnimState(3)
        self.update()
        try:
            self.anim.ExportGIF(file_path, self.res,
                                sample_rate=self.sample_rate,
                                show_watermark=self.show_watermark,
                                frame_hook=self.ExportFrameHook)
        finally:
            self.StopAnimation()

    ############################################################################
    ################################# Settings #################################
    ############################################################################

    def GUI2data(self):
        # The sliders restore through their construction-time initial
        # values, so only the GUI -> data direction lives here
        self.data.kp = self.KpSlider.get()
        self.data.ki = self.KiSlider.get()
        self.data.kd = self.KdSlider.get()
        self.data.watermark = int(self.show_watermark)

    def LoadSetting(self):
        # Missing file or bad lines fall back to the defaults
        data = Setting()
        if self.settingfile.is_file():
            with open(self.settingfile, 'r') as f:
                for line in f.read().split('\n'):
                    temp = line.split('=')
                    if len(temp) < 2:
                        continue
                    try:
                        match temp[0]:
                            case 'kp' | 'ki' | 'kd':
                                setattr(data, temp[0], float(temp[1]))
                            case 'watermark':
                                data.watermark = int(temp[1])
                    except ValueError:
                        pass
        return data

    def WriteSetting(self):
        self.GUI2data()
        with open(self.settingfile, 'w') as f:
            f.write(f'kp={self.data.kp}\n')
            f.write(f'ki={self.data.ki}\n')
            f.write(f'kd={self.data.kd}\n')
            f.write(f'watermark={self.data.watermark}\n')


if __name__ == '__main__':
    app = PIDTeachingAid()
    app.mainloop()
