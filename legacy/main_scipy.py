# -*- coding: utf-8 -*-
from __future__ import division  # 確保 1/2 = 0.5 而非 0
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as ticker
import Tkinter as tk
import ttk
import os
import os.path
import sys
import signal
from scipy import signal

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
        self.root.geometry("1280x720") # 稍微加大視窗以容納動畫區
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)

        # 物理系統參數
        self.m, self.c, self.k = 1.0, 0.5, 2.0
        self.is_ready = False
        
        # 動畫狀態變數
        self.anim_running = False
        self.current_step = 0
        self.sim_data = None
        self.time_data = None # 新增：儲存時間序列供動畫顯示

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
        
        # --- 新增：動畫控制區 ---
        ttk.Label(control_frame, text="Animation", font=('Arial', 12, 'bold')).pack(pady=5)
        self.start_btn = ttk.Button(control_frame, text="Start Animation", command=self.start_animation)
        self.start_btn.pack(fill=tk.X, pady=5)

        # 動畫畫布
        self.anim_canvas = tk.Canvas(control_frame, width=250, height=120, bg="white", highlightthickness=1)
        self.anim_canvas.pack(pady=10)
        self.anim_canvas.create_line(20, 90, 230, 90, fill="#DDD", width=2)
        self.anim_canvas.create_line(150, 30, 150, 90, fill="red", dash=(4, 4))
        self.mass_rect = self.anim_canvas.create_rectangle(30, 60, 70, 90, fill="#1f77b4", outline="#004d99")
        
        # --- 新增：動畫時間顯示文字 ---
        self.time_text = self.anim_canvas.create_text(240, 10, text="Time: 0.00s", anchor='ne', font=('Courier', 10, 'bold'))


        # 繪圖區
        # 建立兩個子圖：ax1 畫位置，ax2 畫控制力
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(7, 8), dpi=90)
        self.fig.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.1, hspace=0.3)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

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

    def stop_animation(self):
        """強制停止動畫並將方塊與時間歸位"""
        self.anim_running = False
        # 將方塊重置到初始位置 (0.0m對應canvas_x=50)
        if hasattr(self, 'mass_rect'):
            self.anim_canvas.coords(self.mass_rect, 30, 60, 70, 90)
        # 重置時間文字
        if hasattr(self, 'time_text'):
            self.anim_canvas.itemconfig(self.time_text, text="Time: 0.00s")

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
        t = np.linspace(0, 16, 513)
        self.time_data = t # 修正：這裡必須將時間軸儲存起來，動畫才能執行

        # 系統建立邏輯
        # 1. 位置 Response 的傳遞函數 (T = CG / 1+CG)
        num_pos = [kd, kp, ki]
        den_pos = [self.m, self.c + kd, self.k + kp, ki]
        
        # 處理 Ki 為 0 的退化情況
        if ki < 0.05:
            num_pos = [kd, kp]
            den_pos = [self.m, self.c + kd, self.k + kp]

        # 計算位置
        sys_pos = signal.TransferFunction(num_pos, den_pos)
        _, y_pos = signal.step(sys_pos, T=t)
        
        self.sim_data = y_pos # 儲存供動畫使用

        # 1. Settling Time (5%) - 判定是否在 16s 內收斂
        threshold = 0.05
        is_converged = False
        settling_time_val = 0.0
        
        # 從最後一點往回找，看最後一個「超出」範圍的點在哪
        for i in range(len(y_pos)-1, -1, -1):
            if abs(y_pos[i] - 1.0) > threshold:
                settling_time_val = t[i]
                # 如果最後一個點 (i=512) 還在範圍外，代表 16s 內沒收斂
                if i == len(y_pos) - 1:
                    is_converged = False
                else:
                    is_converged = True
                break
        else:
            # 如果迴圈沒被 break，代表所有點都在範圍內（極罕見）
            is_converged = True
            settling_time_val = 0.0

        # 2. 根據收斂狀態決定顯示文字
        if is_converged:
            st_text = "%.2fs" % settling_time_val
            sse_text = "%.4f" % abs(1.0 - y_pos[-1])
        else:
            st_text = ">16.00s"
            sse_text = "N/A"

        # 3. Rise Time (10% to 90%)
        idx10 = np.where(y_pos >= 0.1)[0]
        idx90 = np.where(y_pos >= 0.9)[0]
        t10 = t90 = None
        if len(idx10) > 0 and len(idx90) > 0:
            t10, t90 = t[idx10[0]], t[idx90[0]]
            rise_time_val = t90 - t10
            rt_text = "%.2fs" % rise_time_val
        else:
            rt_text = "N/A"

        # 3. Overshoot (OS)
        peak_val = np.max(y_pos)
        peak_idx = np.argmax(y_pos)
        peak_time = t[peak_idx]
        overshoot_pct = max(0, (peak_val - 1.0) / 1.0 * 100) if y_pos[-1] > 0.5 else 0
        

        # 誤差 e = 1 - y_pos
        error = 1.0 - y_pos
        
        # 數值微分 de/dt
        dt = t[1] - t[0]
        de = np.diff(error) / dt
        de = np.append(de, de[-1]) # 補齊長度
        
        # 數值積分 integral(e)
        ie = np.cumsum(error) * dt
        
        # 總控制力 u = Kp*e + Ki*integral(e) + Kd*de/dt
        u_eff = kp * error + ki * ie + kd * de
        

        # 更新圖表 1: 位置
        # --- 繪圖 1: 位置 ---
        self.ax1.clear()
        self.ax1.plot(t, y_pos, color='red', lw=2)
        self.ax1.axhline(1.0, color='black', ls='--', alpha=0.3)

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
        #self.ax1.legend(loc='upper right')
        self.ax1.get_yaxis().set_label_coords(-0.05, 0.5) # 同樣固定在 -0.12 位置
        self.ax1.set_xlim(0, 16)
        self.ax1.grid(True, alpha=0.3)

        # 更新圖表 2: 控制力
        self.ax2.clear()
        self.ax2.plot(t, u_eff, color='blue', lw=1.5)
        self.ax2.set_xlabel("Time (s)")
        self.ax2.set_ylabel("Force (N)")
        self.ax2.get_yaxis().set_label_coords(-0.05, 0.5) # 同樣固定在 -0.12 位置
        #self.ax2.legend(loc='upper right')
        self.ax2.set_xlim(0, 16)
        self.ax2.grid(True, alpha=0.3)

        # 設定科學記號：當數值 > 1000 時觸發
        formatter = ticker.ScalarFormatter(useMathText=True)
        formatter.set_scientific(True)
        formatter.set_powerlimits((-3, 3)) # 超過 10^3 (即1000) 就使用科學記號
        self.ax2.yaxis.set_major_formatter(formatter)
        
        #self.fig.tight_layout()
        self.canvas.draw()

    # --- 動畫邏輯函式 ---
    def start_animation(self):
        if self.anim_running:
            return
        self.anim_running = True
        self.current_step = 0
        self.run_animation_loop()

    def run_animation_loop(self):
        if not self.anim_running or self.sim_data is None or self.time_data is None:
            return
        
        if self.current_step < len(self.sim_data):
            pos = self.sim_data[self.current_step]
            curr_t = self.time_data[self.current_step]
            
            # 更新方塊位置
            canvas_x = 50 + (pos * 100)
            self.anim_canvas.coords(self.mass_rect, canvas_x-20, 60, canvas_x+20, 90)
            
            # 同步更新畫布上的時間文字
            self.anim_canvas.itemconfig(self.time_text, text="Time: %.2fs" % curr_t)
            
            self.current_step += 2 
            self.root.after(20, self.run_animation_loop)
        else:
            self.anim_running = False

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
