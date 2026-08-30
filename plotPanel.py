# -*- coding: utf-8 -*-
# Right-side charts: position response (ax1) and control force (ax2),
# with the performance-metric annotations and the playback cursor
import matplotlib.ticker as ticker
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class PlotPanel:
    def __init__(self, master):
        # Build the Figure directly instead of through pyplot: a
        # pyplot figure manager would promote the process to DPI-aware
        # after tk already measured 96 dpi, shrinking every tk font
        self.fig = Figure(figsize=(7, 8), dpi=90)
        self.ax1, self.ax2 = self.fig.subplots(2, 1)
        self.fig.subplots_adjust(left=0.08, right=0.98,
                                 top=0.95, bottom=0.1, hspace=0.3)
        self.canvas = FigureCanvasTkAgg(self.fig, master=master)
        self.canvas.get_tk_widget().pack(side='right', fill='both',
                                         expand=True)
        # Cursor artists are rebuilt by every UpdatePlot (the axes are
        # cleared there); None until the first plot exists
        self.cursor_dot1  = None
        self.cursor_line1 = None
        self.cursor_dot2  = None
        self.cursor_line2 = None

    def UpdatePlot(self, res, met, target=1.0, theory=None):
        t, y, u = res.t, res.y, res.u
        t_end = t[-1]
        # The charts only format what analyze() found
        rt_text = f'{met.rise_time:4.3f}s' if met.rise_time is not None else 'N/A'
        if met.converged:
            st_text  = f'{met.settling_time:4.3f}s'
            sse_text = f'{met.steady_error:.4f}'
        else:
            st_text  = f'>{t_end:.2f}s'
            sse_text = 'N/A'

        # Chart 1: position response
        self.ax1.clear()
        self.ax1.plot(t, y, color='red', lw=2)
        # Test mode: continuous-time theory overlay in green
        if theory is not None:
            self.ax1.plot(theory.t, theory.y, color='#008000',
                          ls='--', lw=1.5, label='GC/(1+GC) theory')
            self.ax1.legend(loc='upper right', fontsize=8)
        self.ax1.axhline(target, color='black', ls='--', alpha=0.3)
        self.cursor_dot1, = self.ax1.plot([], [], 'ro', markersize=6)
        self.cursor_line1 = self.ax1.axvline(x=0, color='black',
                                             lw=1.5, alpha=0.8)
        self.ax1.text(0.99, 0.56, 'Target position',
                      transform=self.ax1.transAxes,
                      verticalalignment='bottom',
                      horizontalalignment='right',
                      fontdict={'family': 'monospace', 'size': 10})

        perf_info = (f'Rise Time: {rt_text}\n'
                     f'Overshoot: {met.overshoot_pct:4.2f}%\n'
                     f'Settling Time: {st_text}\n'
                     f'Steady Error @ {t_end:.0f}s: {sse_text}')
        self.ax1.text(0.97, 0.05, perf_info, transform=self.ax1.transAxes,
                      verticalalignment='bottom',
                      horizontalalignment='right',
                      bbox=dict(boxstyle='round', facecolor='white',
                                alpha=0.8, edgecolor='#dddddd'),
                      fontdict={'family': 'monospace', 'size': 10})

        # Rise-time band (blue)
        if met.t10 is not None and met.t90 is not None:
            self.ax1.axvspan(met.t10, met.t90, color='#1e90ff', alpha=0.15)
            self.ax1.axvline(met.t10, color='#1e90ff', ls='--',
                             lw=0.8, alpha=0.3)
            self.ax1.axvline(met.t90, color='#1e90ff', ls='--',
                             lw=0.8, alpha=0.3)
            self.ax1.text(met.t90 + 0.6, 0.15, f'Tr={rt_text}',
                          color='blue', ha='center',
                          fontsize=9, fontweight='bold')

        # Settling-time marker (green), only when it converged
        if met.converged and 0 < met.settling_time < t_end:
            self.ax1.axvline(met.settling_time, color='green', ls=':',
                             lw=1.5, alpha=0.7)
            self.ax1.text(met.settling_time, 1.8,
                          f' Ts={met.settling_time:.3f}s',
                          color='green', fontsize=9, fontweight='bold')

        # Overshoot peak marker (orange)
        if met.overshoot_pct > 0.1:
            self.ax1.plot(met.peak_time, met.peak_val, 'o',
                          color='#FF8500', markersize=4)
            self.ax1.annotate(f'Peak: {met.peak_val:.3f}',
                              xy=(met.peak_time, met.peak_val),
                              xytext=(met.peak_time + 0.5, met.peak_val + 0.05),
                              arrowprops=dict(arrowstyle='->', color='#FF8500'),
                              color='#FF8500', fontsize=9)
        self.ax1.set_ylabel('Position (m)')
        self.ax1.set_ylim(-0.2, 2.0)
        self.ax1.get_yaxis().set_label_coords(-0.05, 0.5)
        self.ax1.set_xlim(0, t_end)
        self.ax1.grid(True, alpha=0.3)

        # Chart 2: control force
        self.ax2.clear()
        self.ax2.plot(t, u, color='blue', lw=1.5)
        if theory is not None:
            self.ax2.plot(theory.t, theory.u, color='#008000',
                          ls='--', lw=1.5, label='C/(1+GC) theory')
            self.ax2.legend(loc='upper right', fontsize=8)
        self.cursor_dot2, = self.ax2.plot([], [], 'bo', markersize=6)
        self.cursor_line2 = self.ax2.axvline(x=0, color='black',
                                             lw=1.5, alpha=0.8)
        self.ax2.set_xlabel('Time (s)')
        self.ax2.set_ylabel('Control Force (N)')
        self.ax2.get_yaxis().set_label_coords(-0.05, 0.5)
        self.ax2.set_xlim(0, t_end)
        self.ax2.grid(True, alpha=0.3)

        # Scientific notation once values pass 10^3 (or drop under 10^-3)
        formatter = ticker.ScalarFormatter(useMathText=True)
        formatter.set_scientific(True)
        formatter.set_powerlimits((-3, 3))
        self.ax2.yaxis.set_major_formatter(formatter)

        self.canvas.draw()

    def SetCursor(self, curr_t, pos, curr_u):
        # Move the playback markers; only the artists change, the axes
        # stay as drawn, so draw_idle stays cheap
        if self.cursor_dot1 is None:
            return
        self.cursor_dot1.set_visible(True)
        self.cursor_line1.set_visible(True)
        self.cursor_dot2.set_visible(True)
        self.cursor_line2.set_visible(True)
        self.cursor_dot1.set_data([curr_t], [pos])
        self.cursor_line1.set_xdata([curr_t])
        self.cursor_dot2.set_data([curr_t], [curr_u])
        self.cursor_line2.set_xdata([curr_t])
        self.canvas.draw_idle()

    def HideCursor(self):
        if self.cursor_dot1 is None:
            return
        self.cursor_dot1.set_visible(False)
        self.cursor_line1.set_visible(False)
        self.cursor_dot2.set_visible(False)
        self.cursor_line2.set_visible(False)
        self.canvas.draw_idle()
