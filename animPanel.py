# -*- coding: utf-8 -*-
# Spring-mass animation panel (a small matplotlib figure inside the
# control column) and the GIF exporter that records it
import io
import numpy as np
import matplotlib.offsetbox as offsetbox
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image

from functions import resource_path, get_image_from_b64, HAND_B64


class AnimPanel:
    def __init__(self, master):
        # Scene layout: the mass rest position sits base_offset into
        # the frame, so x = 0 m never touches the wall
        self.base_offset = 0.3
        self.y_center    = -0.25
        self.mass_w      = 0.4
        self.mass_h      = 0.3
        self.rec_zoom    = 3      # export renders at triple resolution
        self.watermark_x = 0.8
        self.watermark_y = 0.5

        # Direct Figure, not pyplot: see the note in plotPanel.py
        self.fig = Figure(figsize=(2.4, 0.9), dpi=100,
                          facecolor='white')
        self.ax  = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=master)
        self.canvas.get_tk_widget().pack(fill='x', pady=10)

        self.ax.set_xlim(-0.2, 2.2)
        self.ax.set_ylim(-0.45, 0.45)
        self.ax.set_aspect('equal')
        self.ax.axis('off')

        # Wall, floor and the target reference line
        self.ax.plot([-0.12, -0.12], [-0.40, 0.0], color='black', lw=4)
        self.ax.plot([-0.12, 2.0], [-0.42, -0.42], color='black', lw=4)
        self.ax.plot([1.3, 1.3], [-0.4, 0.1], color='red',
                     dashes=(2, 2), alpha=0.4, lw=1.5)

        # Spring and mass block
        self.spring_line, = self.ax.plot([], [], color='#777777', lw=1.5)
        self.mass_box = Rectangle((0, 0), 1, 1, fc='#1f77b4',
                                  ec='black', zorder=3)
        self.ax.add_patch(self.mass_box)
        self.center_line, = self.ax.plot([0.5, 0.5], [0, 2],
                                         color='black', lw=1.5)
        self.horiz_line,  = self.ax.plot([0, 0.5], [1, 1],
                                         color='black', lw=1.5)

        # Hand icon: the asset on disk wins, the embedded base64
        # keeps the exe working when the file is missing
        try:
            hand_img = Image.open(resource_path('image0/hand.png'))
        except OSError:
            hand_img = get_image_from_b64(HAND_B64)
        hand_img.thumbnail((100, 100))
        self.hand_box = offsetbox.OffsetImage(hand_img, zoom=1)
        # xybox shifts the icon 25 px right of its anchor, so the hand
        # looks like it pushes the block from the side
        self.hand_annot = offsetbox.AnnotationBbox(self.hand_box, (0, 0),
                                                   xybox=(25, 0),
                                                   xycoords='data',
                                                   boxcoords='offset points',
                                                   frameon=False)
        self.ax.add_artist(self.hand_annot)
        self.hand_annot.set_visible(False)   # shown during playback

        # Live readouts and the export-only parameter card
        font_style     = {'fontname': 'Courier New', 'weight': 'bold',
                          'size': 9.5}
        font_style_rec = {'fontname': 'Courier New', 'weight': 'bold',
                          'size': 5}
        self.time_text  = self.ax.text(0.55, 0.85, '',
                                       transform=self.ax.transAxes,
                                       color='black', **font_style)
        self.force_text = self.ax.text(0.03, 0.69, '',
                                       transform=self.ax.transAxes,
                                       color='blue', **font_style)
        self.displ_text = self.ax.text(0.03, 0.85, '',
                                       transform=self.ax.transAxes,
                                       color='red', **font_style)
        self.param_text = self.ax.text(0.55, 0.70, '',
                                       transform=self.ax.transAxes,
                                       color='black', **font_style_rec)
        self.param_text.set_visible(False)   # shown while exporting

        # Watermark, visible only in exported GIFs
        self.watermark = self.ax.text(self.watermark_x, self.watermark_y,
                                      'CIE5159',
                                      transform=self.ax.transAxes,
                                      fontsize=12, fontweight='bold',
                                      color='gray', alpha=0.3,
                                      rotation=45,
                                      horizontalalignment='center',
                                      verticalalignment='center',
                                      family='sans-serif')
        self.watermark.set_visible(False)

        self.UpdateVisual(0.0, 0.0, 0.0)

    ############################################################################
    ################################ Functions #################################
    ############################################################################

    def get_spring_coords(self, start_x, end_x, y, nodes=8, width=0.15):
        # Zig-zag point list for the spring polyline
        coords = [start_x, y]
        dx = (end_x - start_x) / nodes
        coords.extend([start_x + dx / 2, y])
        for i in range(1, nodes):
            cur_x = start_x + i * dx
            cur_y = y - width if i % 2 == 1 else y + width
            coords.extend([cur_x, cur_y])
        coords.extend([end_x - dx / 2, y])
        coords.extend([end_x, y])
        return coords

    def SetParamText(self, m, c, k, kp, ki, kd):
        line1 = f'm ={m:>5.1f} c ={c:>4.1f} k ={k:>4.1f}\n'
        line2 = f'Kp={kp:>5.1f} Ki={ki:>4.1f} Kd={kd:>4.1f}'
        self.param_text.set_text(line1 + line2)

    def ShowHand(self, on):
        self.hand_annot.set_visible(on)

    def UpdateVisual(self, pos, curr_t, curr_u):
        display_pos = pos + self.base_offset
        y_center = self.y_center
        mass_w, mass_h = self.mass_w, self.mass_h

        self.mass_box.set_xy((display_pos - mass_w / 2,
                              y_center - mass_h / 2))
        self.mass_box.set_width(mass_w)
        self.mass_box.set_height(mass_h)

        # Spring from the wall (-0.1) to the block's left edge
        spring_points = np.array(self.get_spring_coords(
            -0.1, display_pos - mass_w / 2, y_center))
        self.spring_line.set_data(spring_points[0::2], spring_points[1::2])

        self.center_line.set_data(np.array([1, 1]) * display_pos,
                                  np.array([y_center, 0]))
        self.horiz_line.set_data(np.array([0, 0.4]) + display_pos,
                                 np.array([1, 1]) * y_center)
        self.hand_annot.xy = (display_pos + 0.1, y_center)

        self.time_text .set_text(f'Time: {curr_t:.2f} s')
        self.force_text.set_text(f'Force: {curr_u:.2f} N')
        self.displ_text.set_text(f'x = {pos:.2f} m')
        self.canvas.draw_idle()

    def RecordMode(self, on):
        # Export view: bigger hand, parameter card on; the watermark
        # is driven per frame inside ExportGIF
        self.hand_annot.set_visible(on)
        self.hand_box.set_zoom(self.rec_zoom if on else 1)
        self.param_text.set_visible(on)
        if not on:
            self.watermark.set_visible(False)

    def ExportGIF(self, path, res, *, sample_rate=4,
                  show_watermark=True, frame_hook=None):
        # Render every sample_rate-th step of the run into a GIF.
        # frame_hook(pos, t, u) lets the GUI keep its charts and event
        # loop alive between frames without this module importing it
        self.RecordMode(True)
        t_total = res.t[-1]
        dt = res.t[1] - res.t[0]
        frames = []
        try:
            for i in range(0, len(res.y), sample_rate):
                self.UpdateVisual(res.y[i], res.t[i], res.u[i])
                if frame_hook is not None:
                    frame_hook(res.y[i], res.t[i], res.u[i])
                # Watermark slides and spins over one cosine cycle
                self.watermark.set_visible(show_watermark)
                phase = (np.cos(res.t[i] * 2 * np.pi / t_total) + 1) / 2
                self.watermark.set_x(self.watermark_x * phase)
                self.watermark.set_rotation(45 + 360 * phase)
                buf = io.BytesIO()
                self.fig.savefig(buf, format='png', facecolor='white',
                                 dpi=100 * self.rec_zoom)
                buf.seek(0)
                frames.append(Image.open(buf))
            if frames:
                frames[0].save(path, save_all=True,
                               append_images=frames[1:],
                               duration=dt * sample_rate * 1000,
                               loop=0, optimize=True)
        finally:
            self.RecordMode(False)
            self.UpdateVisual(0.0, 0.0, 0.0)
