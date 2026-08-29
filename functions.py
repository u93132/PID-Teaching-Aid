# -*- coding: utf-8 -*-
import base64, io, sys
import tkinter.font as tkfont
from pathlib import Path
from PIL import Image


# Get rid of system language issues
def FindFont():
    families = tkfont.families()
    for name in ('Microsoft JhengHei UI', 'Microsoft Sans Serif'):
        if name in families:
            return name
    return 'calibri'


# For check whether script is in IDLE or Pyinstaller
def resource_path(relative_path):
    # PyInstaller unpacks bundled data files under sys._MEIPASS
    return Path(getattr(sys, '_MEIPASS', '.')) / relative_path


def get_image_from_b64(b64_str):
    # Restore a base64 string into a PIL Image object
    return Image.open(io.BytesIO(base64.b64decode(b64_str)))


# Embedded fallback for image0/hand.png: the file on disk wins when it
# exists, this string keeps the packed exe working without the asset
HAND_B64 = """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
              gg=="""
