# -*- coding: utf-8 -*-
from __future__ import division  # 確保 1/2 = 0.5 而非 0
# Numpy and matplotlib
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker
import matplotlib.font_manager as fm
import matplotlib.offsetbox as offsetbox
# Tkinter
import Tkinter as tk
import ttk
import tkFileDialog
import FileDialog
# PIL
from PIL import Image
# Python library
import base64
import io
import os
import os.path
import sys
import signal

def resource_path(relative_path):
    # Get absolute path to resource, works for dev and for PyInstaller
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

def get_image_from_b64(b64_str):
    """將字串還原為 PIL Image 物件"""
    img_data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_data))


class PIDSimulator(object): # 修改繼承方式以符合原始 root 傳入邏輯
    def on_closing(self):
        # Kill the process for dev or PyInstaller
        try:
            # 先停止更新旗標與動畫
            self.is_ready = False
            self.anim_running = False
            # 關閉所有 matplotlib 建立的 figure 釋放記憶體
            plt.close('all')
            # 判斷是否在 PyInstaller 環境
            base_path = sys._MEIPASS
        except Exception:
            self.root.quit()
            self.root.destroy()
        else:
            os.kill(os.getpid(), signal.SIGTERM)
            
    def __init__(self, root):
        self.root = root
        self.root.title("PID Control Teaching Tool")
        try:
            self.root.iconbitmap(resource_path('image0/Icon.ico'))
        except Exception:
            pass
        self.root.geometry("1280x720+50+30")
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.root.resizable(width=False, height=False)
        self.root.bind('<Control-Key-F2>', self.toggle_watermark)

        # 物理系統參數
        self.m, self.c, self.k = 1.0, 0.5, 2.0
        self.is_ready = False

        # 分析參數
        self.T_total = 16.0
        self.dt = 0.02
        
        # 動畫狀態參數
        self.anim_running = False
        self.current_step = 0
        self.sim_data = None
        self.time_data = None
        self.sample_rate = 4 # 每幾步輸出一幀，這樣設定是 0.02 * 4 * 1000 = 80ms一幀，即12.5FPS
        self.rec_zoom = 3 # 錄影時放大
        self.watermark_x = 0.8
        self.watermark_y = 0.5

        self.setup_ui()
        self.is_ready = True
        self.update_plot()

    def setup_ui(self):
        # 左側控制面板
        control_frame = ttk.Frame(self.root, padding="5")
        control_frame.pack(side=tk.LEFT, fill=tk.Y)

        # 系統參數顯示
        ttk.Label(control_frame, text="Plant Parameters", font=('Arial', 14, 'bold')).pack(pady=5)

        sys_text = "Mass (m): %.2f\nDamping (c): %.2f\nStiffness (k): %.2f" % (self.m, self.c, self.k)
        self.sys_label = ttk.Label(control_frame, text=sys_text, font=('Courier', 11))
        self.sys_label.pack(pady=5)

        ttk.Separator(control_frame, orient='horizontal').pack(fill='x', pady=15)

        # PID參數
        ttk.Label(control_frame, text="PID Parameters", font=('Arial', 14, 'bold')).pack(pady=5)

        # 控制參數顯示
        self.info_label = ttk.Label(control_frame, text="", font=('Courier', 11))
        self.info_label.pack(pady=10)

        # 建立滑桿
        self.kp_slider = self.create_slider(control_frame, "Kp (Proportional)", 0, 100, 20)
        self.ki_slider = self.create_slider(control_frame, "Ki (Integral)", 0, 50, 0)
        self.kd_slider = self.create_slider(control_frame, "Kd (Derivative)", 0, 20, 0)

        guide_text = "Tuning Guide:\n1. Increase Kp for speed\n2. Increase Kd to stop oscillation\n3. Increase Ki to fix offset"
        ttk.Label(control_frame, text=guide_text, foreground="#666").pack(anchor='w', pady=5)

        ttk.Separator(control_frame, orient='horizontal').pack(fill='x', pady=20)
        
        # --- 動畫控制區 ---
        ttk.Label(control_frame, text="Animation Control", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # 使用一個 Frame 來水平排列按鈕
        self.btn_frame = ttk.Frame(control_frame)
        self.btn_frame.pack(fill=tk.X, pady=5)

        self.play_btn = ttk.Button(self.btn_frame, text="Play", width=6, command=self.play_animation)
        self.play_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        self.pause_btn = ttk.Button(self.btn_frame, text="Pause", width=6, command=self.pause_animation)
        self.pause_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        self.stop_btn = ttk.Button(self.btn_frame, text="Stop", width=6, command=self.stop_animation)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        self.export_btn = ttk.Button(self.btn_frame, text="Export", width=6, command=self.export_animation)
        self.export_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        
        # 繪圖區
        # 獨立動畫視窗
        self.fig_anim = plt.figure(figsize=(2.4, 0.9), dpi=100, facecolor='white')
        self.ax_anim = self.fig_anim.add_subplot(111)
        self.fig_anim.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.canvas_anim = FigureCanvasTkAgg(self.fig_anim, master=control_frame)
        self.canvas_anim_widget = self.canvas_anim.get_tk_widget()
        self.canvas_anim_widget.pack(fill=tk.X, pady=10)

        self.ax_anim.clear()
        self.ax_anim.set_xlim(-0.2, 2.2) 
        self.ax_anim.set_ylim(-0.45, 0.45)
        self.ax_anim.set_aspect('equal')
        self.ax_anim.axis('off')

        # 牆壁
        self.ax_anim.plot([-0.12, -0.12], [-0.40, 0.0], color='black', lw=4)
        # 地板
        self.ax_anim.plot([-0.12, 2.0], [-0.42, -0.42], color='black', lw=4)
        # 目標參考線
        self.ax_anim.plot([1.3, 1.3], [-0.4, 0.1], color='red', dashes=(2, 2), alpha=0.4, lw=1.5)

        # 彈簧
        self.spring_line, = self.ax_anim.plot([], [], color='#777777', lw=1.5)
        
        # 質量方塊
        # Rectangle 參數: (x, y), width, height
        self.mass_box = plt.Rectangle((0, 0), 1, 1, fc='#1f77b4', ec='black', zorder=3)
        self.ax_anim.add_patch(self.mass_box)
        # 方塊中央線
        self.center_line, = self.ax_anim.plot([0.5, 0.5], [0, 2], color='black', lw=1.5)
        self.horiz_line, = self.ax_anim.plot([0, 0.5], [1, 1], color='black', lw=1.5)

        # 加入手
        try:
            hand_img = Image.open(resource_path('image0/hand.png'))
        except Exception:
            hand_img = get_image_from_b64(hand)
        # 根據需要調整圖片大小 (例如高度設為 0.2 單位)
        hand_img.thumbnail((100, 100)) # 限制最大像素
        
        # 建立 OffsetImage (將 PIL 轉為 matplotlib 可用的物件)
        # zoom 是縮放倍率，需要根據你的 ax_anim 範圍 (-0.2, 2.2) 微調
        self.hand_box = offsetbox.OffsetImage(hand_img, zoom=1)
        
        # 建立 AnnotationBbox (將圖片貼到特定的 XY 座標)
        # xy=(0,0) 是初始位置，後面會更新
        # xybox=(30, 0) 是圖片相對於 xy 點的偏移量 (像素)，讓手看起來在方塊「右邊」
        # frameon=False 關閉圖片外框
        self.hand_annot = offsetbox.AnnotationBbox(self.hand_box, (0, 0),
                                                    xybox=(25, 0), # 向右偏移 25 像素
                                                    xycoords='data',
                                                    boxcoords="offset points",
                                                    frameon=False)
        
        # 將 Container 加入座標軸
        self.ax_anim.add_artist(self.hand_annot)
        self.hand_annot.set_visible(False) # 預設隱藏，撥放時打開
        
        # 時間與數據文字
        font_style = {'fontname': 'Courier New', 'weight': 'bold', 'size': 9.5}
        font_style_rec = {'fontname': 'Courier New', 'weight': 'bold', 'size': 5}
        self.time_text_display = self.ax_anim.text(0.55, 0.85, '', 
                                                   transform=self.ax_anim.transAxes,
                                                   color='black', **font_style)
        
        # 控制力文字
        self.force_text_display = self.ax_anim.text(0.03, 0.69, '', 
                                                    transform=self.ax_anim.transAxes,
                                                    color='blue', **font_style)
        
        # 位移文字
        self.displ_text_display = self.ax_anim.text(0.03, 0.85, '', 
                                                    transform=self.ax_anim.transAxes,
                                                    color='red', **font_style)

        # 系統參數
        self.param_text = self.ax_anim.text(0.55, 0.70, '', 
                                            transform=self.ax_anim.transAxes,
                                            color='black', **font_style_rec)
        self.param_text.set_visible(False) # 預設隱藏，錄影時打開

        # 浮水印
        self.watermark = self.ax_anim.text(self.watermark_x, self.watermark_y, 'CIE5159', 
                                           transform=self.ax_anim.transAxes,
                                           fontsize=12, fontweight='bold',
                                           color='gray', alpha=0.3, # 半透明
                                           # --- 關鍵修正：旋轉 45 度 ---
                                           rotation=45,
                                           # 對齊基準點改為中心
                                           horizontalalignment='center', 
                                           verticalalignment='center',
                                           family='sans-serif')
        self.show_watermark_flag = True
        self.watermark.set_visible(False) # 錄影才開啟
        
        # 建立兩個子圖：ax1 畫位置，ax2 畫控制力
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(7, 8), dpi=90)
        self.fig.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.1, hspace=0.3)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 初始化動畫窗格
        self.handle_slider_change()
        self.update_canvas_visual(0.0, 0.0, 0.0)

    # 滑桿函數
    def create_slider(self, parent, label, from_, to, initial):
        style = ttk.Style()
        style.configure('Small.TButton', padding=0, width=2, font=('Arial', 5))
        ttk.Label(parent, text=label).pack(anchor='w', pady=(10, 0))
        
        # 建立一個容器來水平排列按鈕與滑桿
        container = ttk.Frame(parent)
        container.pack(fill=tk.X, pady=5)
        
        # 計算 1% 的增量
        step = (to - from_) * 0.01

        # 減號按鈕
        minus_btn = ttk.Button(container, text="-", width=2, style='Small.TButton',
                               command=lambda: self.adjust_slider(slider, -step))
        minus_btn.grid(row=0, column=0, padx=2)

        # 滑桿 (設定 weight=1 讓它自動伸展)
        slider = ttk.Scale(container, from_=from_, to=to, orient=tk.HORIZONTAL, 
                           command=lambda x: self.handle_slider_change() if self.is_ready else None)
        slider.set(initial)
        slider.grid(row=0, column=1, sticky="ew", padx=2)
        container.grid_columnconfigure(1, weight=1)

        # 加號按鈕
        plus_btn = ttk.Button(container, text="+", width=2, style='Small.TButton',
                              command=lambda: self.adjust_slider(slider, step))
        plus_btn.grid(row=0, column=2, padx=2)

        return slider

    def adjust_slider(self, slider, delta):
        """處理按鈕點擊：調整數值並觸發更新"""
        if not self.is_ready: return
        new_val = slider.get() + delta
        # 確保數值不超出滑桿範圍 [from, to]
        # 注意：Tkinter Scale 的 from_ 和 to 是屬性名稱
        min_val = float(slider.cget('from'))
        max_val = float(slider.cget('to'))
        new_val = max(min_val, min(max_val, new_val))
        
        slider.set(new_val)
        self.handle_slider_change()

    def handle_slider_change(self):
        """當滑桿變動時，停止動畫並更新圖表"""
        self.stop_animation()
        self.update_plot()
        # 更新動畫中的系統及控制參數
        kp, ki, kd = self.kp_slider.get(), self.ki_slider.get(), self.kd_slider.get()
        m, c, k = self.m, self.c, self.k
        line1 = "m ={:>5.1f} c ={:>4.1f} k ={:>4.1f}\n".format(m, c, k)
        line2 = "Kp={:>5.1f} Ki={:>4.1f} Kd={:>4.1f}".format(kp, ki, kd)
        
        self.param_text.set_text(line1 + line2)

    def update_plot(self):
        if not self.is_ready or not hasattr(self, 'root'):
            return
        if not hasattr(self, 'ki_slider'):
            return

        kp = float(self.kp_slider.get())
        ki = float(self.ki_slider.get())
        kd = float(self.kd_slider.get())

        self.info_label.config(text="Kp: %6.2f\nKi: %6.2f\nKd: %6.2f" % (kp, ki, kd))

        # 數值模擬設定
        T_total = self.T_total
        dt = self.dt
        steps = int(T_total / dt)+1
        t = np.linspace(0, T_total, steps)
        
        y = np.zeros(steps)
        v = 0.0
        x = 0.0
        integral_e = 0.0
        prev_e = 1.0  # t=0 時誤差為 1.0
        u_out = np.zeros(steps)

        # Forward Euler 求解
        for i in range(steps):
            error = 1.0 - x
            integral_e += error * dt
            derivative_e = (error - prev_e) / dt
            
            # PID 輸出 (控制力)
            u = kp * error + ki * integral_e + kd * derivative_e
            u_out[i] = u
            
            # 物理系統: a = (u - c*v - k*x) / m
            a = (u - self.c * v - self.k * x) / self.m
            v += a * dt
            x += v * dt
            
            y[i] = x
            prev_e = error

        self.sim_data = y
        self.force_data = u_out
        self.time_data = t

        # 1. Settling Time (5%) - 判定是否在 16s 內收斂
        threshold = 0.05
        is_converged = False
        settling_time_val = 0.0
        
        # 從最後一點往回找，看最後一個「超出」範圍的點在哪
        for i in range(len(y)-1, -1, -1):
            if abs(y[i] - 1.0) > threshold:
                settling_time_val = t[i]
                # 如果最後一個點 (i=512) 還在範圍外，代表 16s 內沒收斂
                if i == len(y) - 1:
                    is_converged = False
                else:
                    is_converged = True
                break
        else:
            # 如果迴圈沒被 break，代表所有點都在範圍內（極罕見）
            is_converged = True
            settling_time_val = 0.0

        # 根據收斂狀態決定顯示文字
        if is_converged:
            st_text = "%4.3fs" % settling_time_val
            sse_text = "%.4f" % abs(1.0 - y[-1])
        else:
            st_text = ">16.00s"
            sse_text = "N/A"

        # 2. Rise Time (10% to 90%)
        idx10 = np.where(y >= 0.1)[0]
        idx90 = np.where(y >= 0.9)[0]
        t10 = t90 = None
        if len(idx10) > 0 and len(idx90) > 0:
            t10, t90 = t[idx10[0]], t[idx90[0]]
            rise_time_val = t90 - t10
            rt_text = "%4.3fs" % rise_time_val
        else:
            rt_text = "N/A"

        # 3. Overshoot (OS)
        peak_val = np.max(y)
        peak_idx = np.argmax(y)
        peak_time = t[peak_idx]
        overshoot_pct = max(0, (peak_val - 1.0) / 1.0 * 100) if y[-1] > 0.5 else 0
        

        # 更新圖表 1: 位置
        self.ax1.clear()
        self.ax1.plot(t, y, color='red', lw=2)
        self.ax1.axhline(1.0, color='black', ls='--', alpha=0.3)
        self.cursor_dot1, = self.ax1.plot([], [], 'ro', markersize=6)
        self.cursor_line1 = self.ax1.axvline(x=0, color='black', lw=1.5, alpha=0.8)
        self.ax1.text(0.99, 0.56, 'Target position', transform=self.ax1.transAxes, 
                      verticalalignment='bottom', horizontalalignment='right',
                      fontdict={'family': 'monospace', 'size': 10})

        # --- 更新資訊框內容 ---
        perf_info = "Rise Time: %s\nOvershoot: %4.2f%%\nSettling Time: %s\nSteady Error @ 16s: %s" % (
            rt_text, overshoot_pct, st_text, sse_text)

        self.ax1.text(0.97, 0.05, perf_info, transform=self.ax1.transAxes, 
                      verticalalignment='bottom', horizontalalignment='right',
                      bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='#dddddd'),
                      fontdict={'family': 'monospace', 'size': 10})

        # 標註 Rise Time 線段 (藍色虛線)
        if t10 is not None and t90 is not None:
            # 畫出覆蓋時間區間的半透明色塊 (藍色)
            self.ax1.axvspan(t10, t90, color='#1e90ff', alpha=0.15)
            # 在色塊邊界畫淡藍色虛線
            self.ax1.axvline(t10, color='#1e90ff', ls='--', lw=0.8, alpha=0.3)
            self.ax1.axvline(t90, color='#1e90ff', ls='--', lw=0.8, alpha=0.3)
            # 在兩線中間標註 Tr
            mid_rt = t90 + 0.6
            self.ax1.text(mid_rt, 0.15, 'Tr=%s' % rt_text, color='blue', 
                          ha='center', fontsize=9, fontweight='bold')

        # 只有在收斂時才標註Settling time
        if is_converged and 0 < settling_time_val < 16:
            self.ax1.axvline(settling_time_val, color='green', ls=':', lw=1.5, alpha=0.7)
            self.ax1.text(settling_time_val, 1.8, ' Ts=%.3fs' % settling_time_val, color='green', fontsize=9, fontweight='bold')
        

        # 標註 Overshoot 最高點 (橘色)
        if overshoot_pct > 0.1:
            self.ax1.plot(peak_time, peak_val, 'o', color='#FF8500', markersize=4)
            self.ax1.annotate('Peak: %.3f' % peak_val, xy=(peak_time, peak_val), xytext=(peak_time+0.5, peak_val+0.05),
                              arrowprops=dict(arrowstyle='->', color='#FF8500'), color='#FF8500', fontsize=9)
        self.ax1.set_ylabel("Position (m)")
        self.ax1.set_ylim(-0.2, 2.0)
        self.ax1.get_yaxis().set_label_coords(-0.05, 0.5)
        self.ax1.set_xlim(0, 16)
        self.ax1.grid(True, alpha=0.3)

        # 更新圖表 2: 控制力
        self.ax2.clear()
        self.ax2.plot(t, u_out, color='blue', lw=1.5)
        self.cursor_dot2, = self.ax2.plot([], [], 'bo', markersize=6)
        self.cursor_line2 = self.ax2.axvline(x=0, color='black', lw=1.5, alpha=0.8)
        self.ax2.set_xlabel("Time (s)")
        self.ax2.set_ylabel("Control Force (N)")
        self.ax2.get_yaxis().set_label_coords(-0.05, 0.5)
        self.ax2.set_xlim(0, 16)
        self.ax2.grid(True, alpha=0.3)

        # 設定科學記號：當數值 > 1000 時觸發
        formatter = ticker.ScalarFormatter(useMathText=True)
        formatter.set_scientific(True)
        formatter.set_powerlimits((-3, 3)) # 超過 10^3 或小於 10^-3 就使用科學記號
        self.ax2.yaxis.set_major_formatter(formatter)
        
        #self.fig.tight_layout()
        self.canvas.draw()

    # --- 動畫相關函式 ---
    def play_animation(self):
        self.hand_annot.set_visible(True)
        if not self.anim_running:
            # 初始啟動
            self.anim_running = True
            self.is_paused = False
            self.current_step = 0
            self.run_animation_loop()
        elif self.is_paused:
            # 從暫停中恢復
            self.is_paused = False
            self.run_animation_loop()

    def pause_animation(self):
        if self.anim_running:
            self.is_paused = True

    def stop_animation(self):
        # 停止動畫並初始化
        self.anim_running = False
        self.is_paused = False
        self.current_step = 0
        self.hand_annot.set_visible(False)
        # 視覺歸位
        if hasattr(self, 'fig_anim'):
            self.update_canvas_visual(0.0, 0.0, 0.0)
            # 強制標記回到起點並隱藏
            if hasattr(self, 'cursor_dot1'):
                self.cursor_dot1.set_visible(False)
                self.cursor_line1.set_visible(False)
                self.cursor_dot2.set_visible(False)
                self.cursor_line2.set_visible(False)
                self.canvas.draw_idle()

    def toggle_watermark(self, event=None):
        self.show_watermark_flag = False

    def export_animation(self):
        if self.sim_data is None:
            return

        file_path = tkFileDialog.asksaveasfilename(
            defaultextension=".gif",
            initialfile='PID',
            filetypes=[("GIF Animation", "*.gif")]
        )
        if not file_path: return

        # 按鈕類支援 state=tk.DISABLED
        buttons = [self.play_btn, self.pause_btn, self.stop_btn, self.export_btn]
        # 滑桿類不支援 -state，分開處理
        sliders = [self.kp_slider, self.ki_slider, self.kd_slider]

        for widget in buttons:
            widget.config(state=tk.DISABLED)

        for widget in sliders:
            widget.state(['disabled'])

        # UI 狀態更新
        self.stop_animation()
        self.hand_annot.set_visible(True)
        self.hand_box.set_zoom(self.rec_zoom)
        self.param_text.set_visible(True)
        self.root.update()

        frames = []

        try:
            for i in range(0, len(self.sim_data), self.sample_rate):
                # 1. 更新動畫視覺
                self.update_canvas_visual(self.sim_data[i], self.time_data[i], self.force_data[i])
                self.root.update() # 確保介面有重繪

                # 更新浮水印
                if not self.show_watermark_flag:
                    self.watermark.set_visible(False)
                else:
                    self.watermark.set_visible(True)
                t = self.time_data[i]
                
                new_x = self.watermark_x * ((np.cos(t*2*np.pi/self.T_total)) + 1)/2
                self.watermark.set_x(new_x)
                
                new_angle = 45 + 360 * ((np.cos(t*2*np.pi/self.T_total)) + 1)/2
                self.watermark.set_rotation(new_angle)
                
                # 2. 將當前 Figure 存入記憶體快照 (BytesIO)
                buf = io.BytesIO()
                # 確保背景是白色
                self.fig_anim.savefig(buf, format='png', facecolor='white', dpi=100*self.rec_zoom)
                buf.seek(0)
                
                # 3. 讀取為 PIL 圖像物件
                frames.append(Image.open(buf))

            if frames:
                # 4. 儲存為 GIF
                # duration 是每幀毫秒數
                frames[0].save(
                    file_path,
                    save_all=True,
                    append_images=frames[1:],
                    duration=self.dt*self.sample_rate*1000,
                    loop=0,
                    optimize=True
                )
        finally:
            for widget in buttons:
                widget.config(state=tk.NORMAL)
            for widget in sliders:
                widget.state(['!disabled'])
            self.update_canvas_visual(0.0, 0.0, 0.0)
            self.hand_annot.set_visible(False)
            self.param_text.set_visible(False)
            self.watermark.set_visible(False)
            self.hand_box.set_zoom(1)
            self.stop_animation()

    def run_animation_loop(self):
        """核心動畫循環"""
        # 如果停止、或暫停、或數據遺失，則跳出循環
        if not self.anim_running or self.is_paused or self.sim_data is None: 
            return
        
        if self.current_step < len(self.sim_data):
            pos = self.sim_data[self.current_step]
            curr_t = self.time_data[self.current_step]
            curr_u = self.force_data[self.current_step]
            
            self.update_canvas_visual(pos, curr_t, curr_u)
            
            # 控制撥放速度 (可根據 dt 調整 step 增量)
            self.current_step += 2 
            self.root.after(20, self.run_animation_loop)
        else:
            # 動畫自然結束
            self.anim_running = False

    def get_spring_coords(self, start_x, end_x, y, nodes=8, width=0.15):
        """生成彈簧的鋸齒座標點列表"""
        # 這個版本是給Tkinter canvas，使用matplotlib需要轉格式
        coords = [start_x, y] # 起點
        dx = (end_x - start_x) / nodes
        coords.extend([start_x + dx/2, y])
        for i in range(1, nodes):
            cur_x = start_x + i * dx
            # 奇數點往上偏移，偶數點往下偏移
            cur_y = y - width if i % 2 == 1 else y + width
            coords.extend([cur_x, cur_y])
        coords.extend([end_x - dx/2, y])
        coords.extend([end_x, y]) # 終點
        return coords

    def update_canvas_visual(self, pos, curr_t, curr_u):
        """根據位置與時間更新畫布上的所有元素"""
        # 質量塊中心在 (pos + 偏移)，此處假設 0m 時在圖框 0.3m 處
        base_offset = 0.3
        display_pos = pos + base_offset
        y_center = -0.25
        mass_w = 0.4
        mass_h = 0.3
        
        # 更新方塊狀態
        self.mass_box.set_xy((display_pos - mass_w/2, y_center - mass_h/2))
        self.mass_box.set_width(mass_w)
        self.mass_box.set_height(mass_h)
        
        # 更新彈簧 (從牆壁 -0.1 延伸到方塊左邊緣)
        spring_points = np.array(self.get_spring_coords(-0.1, display_pos - mass_w/2, y_center))
        x_s = spring_points[0::2]
        y_s = spring_points[1::2]
        self.spring_line.set_data(x_s, y_s)

        # 更新中心線
        self.center_line.set_data(np.array([1,1])*(display_pos), np.array([y_center, 0]))
        self.horiz_line.set_data(np.array([0, 0.4])+display_pos, np.array([1,1])*y_center)

        # 更新手
        self.hand_annot.xy = (display_pos+0.1, y_center)

        # 更新文字與畫布
        self.time_text_display.set_text("Time: %.2f s" % curr_t)
        self.force_text_display.set_text("Force: %.2f N" % curr_u)
        self.displ_text_display.set_text("x = %.2f m" % pos)
        self.canvas_anim.draw_idle()


        if hasattr(self, 'cursor_dot1'):
            self.cursor_dot1.set_visible(True)
            self.cursor_line1.set_visible(True)
            self.cursor_dot2.set_visible(True)
            self.cursor_line2.set_visible(True)
            
            # 更新位置圖的點與線
            self.cursor_dot1.set_data([curr_t], [pos])
            self.cursor_line1.set_xdata([curr_t])
            
            # 更新控制力圖的點與線
            self.cursor_dot2.set_data([curr_t], [curr_u])
            self.cursor_line2.set_xdata([curr_t])
            
            # 重新繪製圖表 (重點：只更新背景數據而不重刷整個軸可以提高效能)
            self.canvas.draw_idle()

if __name__ == "__main__":
    root = tk.Tk()
    hand = """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
              gg==""".strip()
    style = ttk.Style()
    # 確保在舊版環境中也能有較現代的 UI 視覺
    try:
        style.theme_use('clam')
    except:
        pass
    app = PIDSimulator(root)
    root.mainloop()
