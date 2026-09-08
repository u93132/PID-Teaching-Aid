# -*- coding: utf-8 -*-
import os, sys, signal, tempfile
from dataclasses import dataclass
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog

from functions import *
from boxBase import *
from simulation import simulate, simulate_theory, analyze
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
    # Plant (mass-spring-damper). Adjustable in Ctrl+F2 test mode only;
    # these defaults are the textbook plant students always see
    m: float = 1.0
    c: float = 0.5
    k: float = 2.0


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
        w = 960
        h = 640
        x = (ws / 2) - (w / 2)
        y = (hs / 2) - (h / 2)
        self.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
        self.resizable(width=False, height=False)
        self.bind('<Control-Key-F2>', self.ToggleTestMode)
        # ttk styles
        style = ttk.Style()
        style.theme_create('MyStyle', parent='alt', settings={
            'TNotebook':     {'configure': {'tabmargins': [2, 2, 2, 0]}},
            'TNotebook.Tab': {'configure': {'padding':    [5, 0]}},
            'TCombobox':     {'configure': {'padding': 2, 'arrowsize': 15}},
            'TFrame':        {'configure': {'background': 'SystemButtonFace'}},
            'TLabel':        {'configure': {'background': 'SystemButtonFace',
                                            'foreground': 'SystemButtonText'}},
        })
        style.theme_use('MyStyle')
        # Plant parameters: read from the Plant sliders in UpdatePlot()
        self.m = self.c = self.k = None
        # Simulation setup
        self.t_total = 16.0
        self.dt      = 0.02
        # Animation state
        self.is_ready     = False
        self.anim_running = False
        self.is_paused    = False
        self.current_step = 0
        self.anim_state   = 0   # last value passed to AnimState()
        self.res = None   # latest SimResult
        self.met = None   # latest Metrics
        self.sample_rate = 4   # export: one frame per 4 steps = 12.5 FPS
        # Settings
        self.settingfile = Path(tempfile.gettempdir()) / 'PIDTeachingAid.txt'
        self.data = self.LoadSetting()
        # Test mode (Ctrl+F2): theory overlay on the charts and no
        # watermark in exports. Stored inverted as the watermark flag
        self.test_mode = not bool(self.data.watermark)
        if not self.test_mode:
            # Outside test mode the plant is always the textbook one,
            # whatever a hand-edited settings file says
            d = Setting()
            self.data.m, self.data.c, self.data.k = d.m, d.c, d.k

        ########################################################################
        ####################### GUI objects : Control Panel ####################
        ########################################################################

        self.controlframe = ttk.Frame(self, padding='5')
        self.controlframe.pack(side='left', fill='y')
        # Notebook: Plant | PID
        self.nb = ttk.Notebook(self.controlframe)
        self.nb.pack(fill='x', pady=5)
        self.nb.framename = ['Plant', 'PID']
        self.nb.frame = [None] * len(self.nb.framename)
        for i, name in enumerate(self.nb.framename):
            self.nb.frame[i] = tk.Frame(self.nb)
            self.nb.frame[i].config(height=320, width=260)
            self.nb.frame[i].pack()
            self.nb.add(self.nb.frame[i], text=name)
        plant_frame = tk.Frame(self.nb.frame[0], padx=8, pady=5)
        plant_frame.pack(fill='x', anchor='nw')
        pid_frame   = tk.Frame(self.nb.frame[1], padx=8, pady=5)
        pid_frame.pack(fill='x', anchor='nw')
        # Plant tab: m / c / k readout and sliders. The sliders are
        # hidden outside Ctrl+F2 test mode (decided in AnimState). m has
        # a floor because plant_accel divides by it
        self.SysLabel = ttk.Label(plant_frame, text='',
                                  font=('Courier', 11))
        self.SysLabel.pack(pady=5)
        self.MSlider = SliderBox(plant_frame, 'Mass (m)',
                                 0.1, 5.0, self.data.m,
                                 self.HandleSliderChange)
        self.CSlider = SliderBox(plant_frame, 'Damping (c)',
                                 0.0, 5.0, self.data.c,
                                 self.HandleSliderChange)
        self.KSlider = SliderBox(plant_frame, 'Stiffness (k)',
                                 0.0, 10.0, self.data.k,
                                 self.HandleSliderChange)
        self.plant_sliders = [self.MSlider, self.CSlider, self.KSlider]
        # PID tab: gain readout, sliders, tuning guide
        self.InfoLabel = ttk.Label(pid_frame, text='',
                                   font=('Courier', 11))
        self.InfoLabel.pack(pady=5)
        self.KpSlider = SliderBox(pid_frame, 'Kp (Proportional)',
                                  0, 100, self.data.kp,
                                  self.HandleSliderChange)
        self.KiSlider = SliderBox(pid_frame, 'Ki (Integral)',
                                  0, 50, self.data.ki,
                                  self.HandleSliderChange)
        self.KdSlider = SliderBox(pid_frame, 'Kd (Derivative)',
                                  0, 20, self.data.kd,
                                  self.HandleSliderChange)
        self.sliders = [self.KpSlider, self.KiSlider, self.KdSlider]
        guide_text = ('Tuning Guide:\n'
                      '1. Increase Kp for speed\n'
                      '2. Increase Kd to stop oscillation\n'
                      '3. Increase Ki to fix offset')
        ttk.Label(pid_frame, text=guide_text,
                  foreground='#666').pack(anchor='w', pady=5)
        self.nb.select(1)

        ########################################################################
        ###################### GUI objects : Animation Control #################
        ########################################################################

        ttk.Label(self.controlframe, text='Animation Control',
                  font=('Arial', 12, 'bold')).pack(pady=5)
        self.btnframe = ttk.Frame(self.controlframe)
        self.btnframe.pack(fill='x', pady=5)
        self.PlayButton   = tk.Button(self.btnframe, text='Play', width=6,
                                      command=self.PlayAnimation)
        self.PlayButton   .pack(side='left', expand=True, fill='x', padx=1)
        self.PauseButton  = tk.Button(self.btnframe, text='Pause', width=6,
                                      command=self.PauseAnimation)
        self.PauseButton  .pack(side='left', expand=True, fill='x', padx=1)
        self.StopButton   = tk.Button(self.btnframe, text='Stop', width=6,
                                      command=self.StopAnimation)
        self.StopButton   .pack(side='left', expand=True, fill='x', padx=1)
        self.ExportButton = tk.Button(self.btnframe, text='Export', width=6,
                                      command=self.ExportAnimation)
        self.ExportButton .pack(side='left', expand=True, fill='x', padx=1)
        ToolTip(self.PlayButton,   'Play the response animation')
        ToolTip(self.PauseButton,  'Pause the animation')
        ToolTip(self.StopButton,   'Stop and rewind the animation')
        ToolTip(self.ExportButton, 'Export the animation as a GIF\n'
                                   '(Ctrl+F2: test mode - theory\n'
                                   ' overlay, no watermark)')
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
        self.anim_state = i
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
        # The plant sliders exist only in test mode and unlock only at idle
        for s in self.plant_sliders:
            s.Show(self.test_mode)
            s.SetState(i == 0 and self.test_mode)

    def HandleSliderChange(self):
        # Any gain or plant change stops the playback and redraws
        if not self.is_ready:
            return
        self.StopAnimation()
        self.UpdatePlot()

    def UpdatePlot(self):
        kp = self.KpSlider.get()
        ki = self.KiSlider.get()
        kd = self.KdSlider.get()
        self.m = self.MSlider.get()
        self.c = self.CSlider.get()
        self.k = self.KSlider.get()
        self.SysLabel.config(text=(f'{"Mass (m):":<15}{self.m:.2f}\n'
                                   f'{"Damping (c):":<15}{self.c:.2f}\n'
                                   f'{"Stiffness (k):":<15}{self.k:.2f}'))
        self.InfoLabel.config(text=(f'Kp: {kp:6.2f}\n'
                                    f'Ki: {ki:6.2f}\n'
                                    f'Kd: {kd:6.2f}'))
        self.res = simulate(kp, ki, kd, m=self.m, c=self.c, k=self.k,
                            t_total=self.t_total, dt=self.dt)
        self.met = analyze(self.res.t, self.res.y)
        # Test mode overlays the continuous-time closed-loop theory
        theory = None
        if self.test_mode:
            theory = simulate_theory(kp, ki, kd, m=self.m, c=self.c,
                                     k=self.k, t_total=self.t_total,
                                     dt=self.dt)
        self.plot.UpdatePlot(self.res, self.met, theory=theory)
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

    def ToggleTestMode(self, event=None):
        self.test_mode = not self.test_mode
        if not self.test_mode:
            # Leaving test mode puts the textbook plant back. Set the
            # sliders silently (is_ready gates their callback), then
            # stop like any other plant change and redraw once below
            d = Setting()
            ready, self.is_ready = self.is_ready, False
            self.MSlider.set(d.m)
            self.CSlider.set(d.c)
            self.KSlider.set(d.k)
            self.is_ready = ready
            self.StopAnimation()
        self.UpdatePlot()
        # Re-apply the current state so the plant sliders follow test_mode
        self.AnimState(self.anim_state)

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
                                show_watermark=not self.test_mode,
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
        self.data.m  = self.MSlider.get()
        self.data.c  = self.CSlider.get()
        self.data.k  = self.KSlider.get()
        self.data.watermark = int(not self.test_mode)

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
                            case 'kp' | 'ki' | 'kd' | 'm' | 'c' | 'k':
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
            f.write(f'm={self.data.m}\n')
            f.write(f'c={self.data.c}\n')
            f.write(f'k={self.data.k}\n')
            f.write(f'watermark={self.data.watermark}\n')


if __name__ == '__main__':
    app = PIDTeachingAid()
    app.mainloop()
