# -*- coding: utf-8 -*-
# Regression test: the app must leave the process DPI-unaware, like
# ShinyHunterUSUM, so Windows scales the whole window and tk fonts
# keep their size on scaled displays. matplotlib's Tk backend promotes
# the process to per-monitor aware whenever a pyplot figure manager is
# created, which shrinks every tk font measured at 96 dpi.
# Run from the repo root:  py -3 -m unittest discover tests
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = '''
import ctypes
from PIDTeachingAid_GUI import PIDTeachingAid
app = PIDTeachingAid()
app.update()
aw = ctypes.c_int()
ctypes.OleDLL('shcore').GetProcessDpiAwareness(None, ctypes.byref(aw))
app.destroy()
print(aw.value)
'''


@unittest.skipUnless(sys.platform == 'win32', 'Windows DPI behavior')
class TestDpiAwareness(unittest.TestCase):
    def test_process_stays_dpi_unaware(self):
        # A fresh process is required: DPI awareness sticks per process
        proc = subprocess.run([sys.executable, '-c', PROBE],
                              cwd=ROOT, capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # 0 = PROCESS_DPI_UNAWARE
        self.assertEqual(proc.stdout.strip(), '0',
                         'the GUI promoted the process DPI awareness: '
                         f'{proc.stdout!r}')


if __name__ == '__main__':
    unittest.main()
