# -*- coding: utf-8 -*-
# GUI-level tests for the Ctrl+F2 plant sliders (m / c / k). The real
# app is built withdrawn - no mainloop, nothing shown - and driven by
# direct method calls, so this stays inside unittest discovery.
# Run from the repo root:  py -3 -m unittest discover tests
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Hard watchdog: a stuck Tk call must fail the run, never hang it
def _watchdog():
    time.sleep(120)
    print('test_gui_plant: watchdog timeout', flush=True)
    os._exit(2)


threading.Thread(target=_watchdog, daemon=True).start()

from PIDTeachingAid_GUI import PIDTeachingAid, Setting   # noqa: E402

TEXTBOOK = (Setting().m, Setting().c, Setting().k)


def enabled(slider):
    # A SliderBox is usable only when the scale and both nudge buttons are
    return ('disabled' not in slider.Scale.state()
            and str(slider.MinusButton['state']) == 'normal'
            and str(slider.PlusButton['state']) == 'normal')


def visible(slider):
    # winfo_manager() is '' once pack_forget() has removed the widget;
    # winfo_ismapped() would need a mapped (non-withdrawn) window
    return (slider.label.winfo_manager() == 'pack'
            and slider.frame.winfo_manager() == 'pack')


class TestPlantSliders(unittest.TestCase):
    def setUp(self):
        self.app = PIDTeachingAid()
        self.app.withdraw()
        # Never touch the user's real settings file
        self.tmp = tempfile.TemporaryDirectory()
        self.app.settingfile = Path(self.tmp.name) / 'PIDTeachingAid.txt'
        # Every test starts outside test mode with the textbook plant,
        # whatever the real settings file restored
        if self.app.test_mode:
            self.app.ToggleTestMode()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def assertPlant(self, m, c, k):
        self.assertAlmostEqual(self.app.m, m)
        self.assertAlmostEqual(self.app.c, c)
        self.assertAlmostEqual(self.app.k, k)

    def test_hidden_outside_test_mode(self):
        self.assertPlant(*TEXTBOOK)
        for s in self.app.plant_sliders:
            self.assertFalse(visible(s), 'plant slider shown')
            self.assertFalse(enabled(s), 'plant slider unlocked')
        # The readout stays: students still see the plant values
        self.assertEqual(self.app.SysLabel.winfo_manager(), 'pack')
        # Gain sliders are never gated by test mode
        for s in self.app.sliders:
            self.assertTrue(visible(s) and enabled(s),
                            'gain slider hidden or locked at idle')

    def test_shown_and_unlocked_when_idle_in_test_mode(self):
        self.app.ToggleTestMode()
        self.assertTrue(self.app.test_mode)
        for s in self.app.plant_sliders:
            self.assertTrue(visible(s), 'plant slider hidden')
            self.assertTrue(enabled(s), 'plant slider still locked')

    def test_reshow_keeps_plant_tab_order(self):
        # Re-showing appends to the pack order, so the block must come
        # back as readout, m, c, k - not shuffled
        self.app.ToggleTestMode()
        self.app.ToggleTestMode()
        self.app.ToggleTestMode()
        want = [self.app.SysLabel]
        for s in self.app.plant_sliders:
            want += [s.label, s.frame]
        self.assertEqual(self.app.SysLabel.master.pack_slaves(), want)

    def test_shown_but_locked_while_busy_in_test_mode(self):
        self.app.ToggleTestMode()
        for state in (1, 2, 3):
            self.app.AnimState(state)
            for s in self.app.plant_sliders:
                self.assertTrue(visible(s),
                                f'plant slider hidden in state {state}')
                self.assertFalse(enabled(s),
                                 f'plant slider unlocked in state {state}')
        self.app.AnimState(0)
        for s in self.app.plant_sliders:
            self.assertTrue(enabled(s), 'plant slider not restored at idle')

    def test_plant_change_drives_simulation(self):
        # P-only steady state is kp/(k+kp): a stiffer spring pulls it
        # down. Kd adds damping so the run settles inside t_total
        self.app.ToggleTestMode()
        self.app.KpSlider.set(20.0)
        self.app.KiSlider.set(0.0)
        self.app.KdSlider.set(5.0)
        self.app.KSlider.set(8.0)     # fires HandleSliderChange
        self.assertAlmostEqual(self.app.k, 8.0)
        self.assertAlmostEqual(self.app.res.y[-1], 20.0 / 28.0, places=2)
        self.assertIn('8.00', self.app.SysLabel['text'])

    def test_set_lands_on_locked_slider(self):
        # Regression: a disabled ttk.Scale ignores set(), which used to
        # swallow the plant reset when leaving test mode mid-playback.
        # Hidden widgets still hold state, so this works while hidden too
        s = self.app.MSlider
        self.assertFalse(enabled(s) or visible(s))
        s.set(2.0)
        self.assertAlmostEqual(s.get(), 2.0)
        self.assertFalse(enabled(s), 'set() must not unlock the slider')

    def test_mass_floor_keeps_plant_regular(self):
        # The scale clamps to its range, so m can never reach zero
        self.app.ToggleTestMode()
        self.app.MSlider.set(0.0)
        self.assertGreaterEqual(self.app.m, 0.1)

    def test_leaving_test_mode_resets_plant_and_stops(self):
        self.app.ToggleTestMode()
        self.app.MSlider.set(3.0)
        self.app.CSlider.set(2.0)
        self.app.KSlider.set(9.0)
        self.assertPlant(3.0, 2.0, 9.0)
        self.app.PlayAnimation()
        self.assertTrue(self.app.anim_running)
        self.app.ToggleTestMode()
        self.assertFalse(self.app.test_mode)
        self.assertPlant(*TEXTBOOK)
        # A plant change stops playback, like a gain change does
        self.assertFalse(self.app.anim_running)
        self.assertEqual(self.app.current_step, 0)
        for s in self.app.plant_sliders:
            self.assertFalse(visible(s), 'plant slider shown after exit')

    def test_setting_round_trip(self):
        self.app.ToggleTestMode()
        self.app.MSlider.set(2.5)
        self.app.CSlider.set(1.25)
        self.app.KSlider.set(7.0)
        self.app.WriteSetting()
        data = self.app.LoadSetting()
        self.assertAlmostEqual(data.m, 2.5)
        self.assertAlmostEqual(data.c, 1.25)
        self.assertAlmostEqual(data.k, 7.0)
        self.assertEqual(data.watermark, 0)   # still in test mode

    def test_legacy_file_without_plant_keys(self):
        # Settings written before this feature carry no m/c/k lines
        self.app.settingfile.write_text('kp=30.0\nwatermark=1\n')
        data = self.app.LoadSetting()
        self.assertEqual(data.kp, 30.0)
        self.assertEqual((data.m, data.c, data.k), TEXTBOOK)


if __name__ == '__main__':
    unittest.main()
