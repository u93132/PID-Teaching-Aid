# Manual GUI smoke test: drive the app through its own mainloop with
# after()-scheduled steps. Prints SMOKE-OK / SMOKE-FAIL and exits.
# A hard watchdog (os._exit) guarantees the process never hangs.
# Named without the test_ prefix on purpose: it opens a real window
# for a few seconds, so unittest discovery must not pick it up.
# Run from anywhere:  py -3 tests/manual_smoke_gui.py
import sys, os, threading, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)   # resource_path uses '.'

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

WATCHDOG_S = 60
def watchdog():
    time.sleep(WATCHDOG_S)
    print('SMOKE-FAIL: watchdog timeout', flush=True)
    os._exit(2)
threading.Thread(target=watchdog, daemon=True).start()

import traceback
def report_callback_exception(exc, val, tb):
    print('SMOKE-FAIL: exception in tk callback:', flush=True)
    traceback.print_exception(exc, val, tb)
    os._exit(3)

from PIDTeachingAid_GUI import PIDTeachingAid

app = PIDTeachingAid()
app.report_callback_exception = report_callback_exception
failures = []

def check(cond, msg):
    if not cond:
        failures.append(msg)

def finish():
    print('-> finish', flush=True)
    app.quit()

def step1():
    print('-> step1', flush=True)
    # Idle state after startup
    check(str(app.PlayButton['state']) == 'normal', 'play not enabled at idle')
    check(str(app.PauseButton['state']) == 'disabled', 'pause enabled at idle')
    check(app.res is not None and len(app.res.y) == 801, 'no simulation result')
    # Gain change redraws and stays idle
    app.KpSlider.set(40)
    app.after(200, step2)

def step2():
    print('-> step2', flush=True)
    check(abs(app.KpSlider.get() - 40) < 1e-6, 'slider set failed')
    check(str(app.ExportButton['state']) == 'normal', 'export disabled at idle')
    # Ctrl+F2 test mode: theory overlay redraw must not blow up
    was = app.test_mode
    app.ToggleTestMode()
    check(app.test_mode == (not was), 'test mode did not toggle')
    if not app.test_mode:
        app.ToggleTestMode()   # make sure playback runs with overlay on
    # Plant sliders appear only in test mode, unlocked at idle
    check(all(s.frame.winfo_manager() == 'pack' for s in app.plant_sliders),
          'plant sliders hidden in test mode')
    check(all('disabled' not in s.Scale.state() for s in app.plant_sliders),
          'plant sliders locked in test mode')
    app.PlayAnimation()
    app.after(400, step3)

def step3():
    print('-> step3', flush=True)
    check(app.anim_running, 'animation did not start')
    check(app.current_step > 0, 'animation loop did not advance')
    check(str(app.PlayButton['state']) == 'disabled', 'play enabled while playing')
    check(str(app.PauseButton['state']) == 'normal', 'pause disabled while playing')
    check(all('disabled' in s.Scale.state() for s in app.plant_sliders),
          'plant sliders unlocked while playing')
    app.PauseAnimation()
    app.after(100, step4)

step_at_pause = None
def step4():
    print('-> step4', flush=True)
    global step_at_pause
    step_at_pause = app.current_step
    check(str(app.PlayButton['state']) == 'normal', 'play disabled while paused')
    app.after(300, step5)

def step5():
    print('-> step5', flush=True)
    check(app.current_step == step_at_pause, 'animation ran while paused')
    app.PlayAnimation()   # resume
    app.after(200, step6)

def step6():
    print('-> step6', flush=True)
    check(app.anim_running and not app.is_paused, 'resume failed')
    app.StopAnimation()
    check(not app.anim_running and app.current_step == 0, 'stop did not reset')
    check(str(app.StopButton['state']) == 'disabled', 'stop enabled at idle')
    # Back to normal mode, then settings round trip
    if app.test_mode:
        app.ToggleTestMode()
    check(not app.test_mode, 'test mode stuck on')
    check((app.m, app.c, app.k) == (1.0, 0.5, 2.0),
          'plant not reset on leaving test mode')
    check(all(s.frame.winfo_manager() == '' for s in app.plant_sliders),
          'plant sliders shown outside test mode')
    app.WriteSetting()
    reloaded = app.LoadSetting()
    check(abs(reloaded.kp - 40) < 1e-6, 'setting kp did not persist')
    check(reloaded.watermark == 1, 'watermark flag did not persist')
    # GIF export pipeline on a short slice of the run (5 frames)
    from simulation import SimResult
    small = SimResult(t=app.res.t[:20], y=app.res.y[:20], u=app.res.u[:20])
    gif = os.path.join(os.environ['TEMP'], 'smoke_pid.gif')
    app.anim.ExportGIF(gif, small, sample_rate=4)
    with open(gif, 'rb') as f:
        check(f.read(6) in (b'GIF87a', b'GIF89a'), 'export is not a GIF')
    os.remove(gif)
    app.after(100, finish)

app.after(300, step1)
app.mainloop()
app.destroy()

if failures:
    print('SMOKE-FAIL:', '; '.join(failures))
    sys.exit(1)
print('SMOKE-OK')
