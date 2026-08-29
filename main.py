# -*- coding: utf-8 -*-
from __future__ import division  # 確保 1/2 = 0.5 而非 0
# Numpy and matplotlib
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker
# Tkinter
import Tkinter as tk
import ttk
import tkFileDialog
import FileDialog
# Python library
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
            plt.close(self.fig)
            plt.close('all')
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

        # 物理系統參數
        self.m, self.c, self.k = 1.0, 0.5, 2.0
        self.is_ready = False
        
        # 動畫狀態參數
        self.anim_running = False
        self.current_step = 0
        self.sim_data = None
        self.time_data = None

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

        # 數值顯示 (使用 % 格式化，因為 Python 2.7 較常用此方式)
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

        # 動畫畫布
        self.anim_canvas = tk.Canvas(control_frame, width=250, height=120, bg="white", highlightthickness=1)
        self.anim_canvas.pack(pady=10)
        
        # 初始化彈簧 (這是一條多段線，初始座標先隨便給，後續會更新)
        self.spring_line = self.anim_canvas.create_line(0, 0, 0, 0, fill="#777", width=2)
        
        # 繪製牆壁、地板與參考線
        self.anim_canvas.create_rectangle(5, 40, 10, 100, fill="black")    # 牆壁
        self.anim_canvas.create_rectangle(10, 90, 230, 95, fill="black")    # 地板
        self.anim_canvas.create_line(150, 30, 150, 90, fill="red", dash=(4, 4)) # 目標位置
        self.mass_rect = self.anim_canvas.create_rectangle(30, 60, 70, 90, fill="#1f77b4", outline="#004d99")
        self.center_line = self.anim_canvas.create_line(0, 0, 0, 0, fill="black", width=2)
        
        # --- 新增：動畫時間顯示文字 ---
        self.time_text = self.anim_canvas.create_text(240, 5, text="Time: 0.00s", anchor='ne', font=('Courier', 10, 'bold'))
        self.displ_text_display = self.anim_canvas.create_text(10, 5, text="x =  0.00 m", anchor='nw', font=('Courier', 10, 'bold'))
        self.force_text_display = self.anim_canvas.create_text(10, 18, text="Force: 0.00 N", anchor='nw', font=('Courier', 10, 'bold'))

        # 初始化動畫窗格
        self.update_canvas_visual(0.0, 0.0, 0.0)
        
        # 繪圖區
        # 建立兩個子圖：ax1 畫位置，ax2 畫控制力
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(7, 8), dpi=90)
        self.fig.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.1, hspace=0.3)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # 滑桿函數
    def create_slider(self, parent, label, from_, to, initial):
        ttk.Label(parent, text=label).pack(anchor='w', pady=(10, 0))
        # 使用 lambda 時需判斷 self.is_ready
        slider = ttk.Scale(parent, from_=from_, to=to, orient=tk.HORIZONTAL, 
                           command=lambda x: self.handle_slider_change() if self.is_ready else None)
        slider.set(initial)
        slider.pack(pady=5, fill=tk.X)
        return slider

    def handle_slider_change(self):
        """當滑桿變動時，停止動畫並更新圖表"""
        self.stop_animation()
        self.update_plot()

    def update_plot(self):
        # 加上更嚴格的檢查，如果視窗已不存在就跳出
        if not self.is_ready or not hasattr(self, 'root'):
            return
        # 確保所有元件已初始化
        if not hasattr(self, 'ki_slider'):
            return

        kp = float(self.kp_slider.get())
        ki = float(self.ki_slider.get())
        kd = float(self.kd_slider.get())

        self.info_label.config(text="Kp: %6.2f\nKi: %6.2f\nKd: %6.2f" % (kp, ki, kd))

        # 數值模擬設定
        T_total = 16.0
        dt = 0.02
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
            
            # 物理系統: a = (F - c*v - k*x) / m
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
            st_text = "%.2fs" % settling_time_val
            sse_text = "%.4f" % abs(1.0 - y[-1])
        else:
            st_text = ">16.00s"
            sse_text = "N/A"

        # 3. Rise Time (10% to 90%)
        idx10 = np.where(y >= 0.1)[0]
        idx90 = np.where(y >= 0.9)[0]
        t10 = t90 = None
        if len(idx10) > 0 and len(idx90) > 0:
            t10, t90 = t[idx10[0]], t[idx90[0]]
            rise_time_val = t90 - t10
            rt_text = "%.2fs" % rise_time_val
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
        perf_info = "Rise Time: %s\nOvershoot: %.1f%%\nSettling Time: %s\nSteady Error @ 16s: %s" % (
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

        # 只有在收斂時才畫垂直線
        if is_converged and 0 < settling_time_val < 16:
            self.ax1.axvline(settling_time_val, color='green', ls=':', lw=1.5, alpha=0.7)
            self.ax1.text(settling_time_val, 1.8, ' Ts=%.2fs' % settling_time_val, color='green', fontsize=9, fontweight='bold')
        

        # 標註 Overshoot 最高點 (橘色)
        if overshoot_pct > 0.1:
            self.ax1.plot(peak_time, peak_val, 'o', color='orange', markersize=4)
            self.ax1.annotate('Peak: %.2f' % peak_val, xy=(peak_time, peak_val), xytext=(peak_time+0.5, peak_val+0.05),
                              arrowprops=dict(arrowstyle='->', color='orange'), color='orange', fontsize=9)
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
        formatter.set_powerlimits((-3, 3)) # 超過 10^3 (即1000) 就使用科學記號
        self.ax2.yaxis.set_major_formatter(formatter)
        
        #self.fig.tight_layout()
        self.canvas.draw()

    # --- 動畫相關函式 ---
    def play_animation(self):
        """開始或從暫停中恢復動畫"""
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
        """暫停動畫"""
        if self.anim_running:
            self.is_paused = True

    def stop_animation(self):
        """停止動畫並重置所有狀態"""
        self.anim_running = False
        self.is_paused = False
        self.current_step = 0
        # 視覺歸位
        if hasattr(self, 'anim_canvas'):
            self.update_canvas_visual(0.0, 0.0, 0.0)
            # 強制標記回到起點
            if hasattr(self, 'cursor_dot1'):
                self.cursor_dot1.set_visible(False)
                self.cursor_line1.set_visible(False)
                self.cursor_dot2.set_visible(False)
                self.cursor_line2.set_visible(False)
                self.canvas.draw_idle()

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

    def get_spring_coords(self, start_x, end_x, y, nodes=8, width=15):
        """生成彈簧的鋸齒座標點列表"""
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
        # 計算方塊位置 (0.0m 偏移量為 50)
        center_x = 50 + (pos * 100)
        left_edge = center_x - 20
        right_edge = center_x + 20
        
        # 更新方塊
        if hasattr(self, 'mass_rect'):
            self.anim_canvas.coords(self.mass_rect, left_edge, 60, right_edge, 90)

        # 更新黑色中心線 (垂直貫穿方塊)
        if hasattr(self, 'center_line'):
            self.anim_canvas.coords(self.center_line, center_x, 75, center_x, 45)
        
        # 更新彈簧 (從牆壁 x=10 到方塊左側 left_edge)
        spring_points = self.get_spring_coords(10, left_edge, 75)
        if hasattr(self, 'spring_line'):
            self.anim_canvas.coords(self.spring_line, *spring_points)
        
        # 更新時間文字
        if hasattr(self, 'time_text'):
            self.anim_canvas.itemconfig(self.time_text, text="Time: %.2fs" % curr_t)

        # 更新時間文字    
        if hasattr(self, 'force_text_display'):
            self.anim_canvas.itemconfig(self.force_text_display, fill="blue", text="Force: %.2f N" % curr_u)

        if hasattr(self, 'displ_text_display'):
            self.anim_canvas.itemconfig(self.displ_text_display, fill="red", text="x = : %.2f m" % pos)

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
    style = ttk.Style()
    # 確保在舊版環境中也能有較現代的 UI 視覺
    try:
        style.theme_use('clam')
    except:
        pass
    app = PIDSimulator(root)
    root.mainloop()
