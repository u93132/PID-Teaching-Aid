# PID Teaching Aid
A Python-based PID teaching aid: tune Kp / Ki / Kd on a mass-spring-damper
plant and watch the step response, control force, performance metrics
(rise time, overshoot, settling time, steady-state error) and a spring-mass
animation update live. The animation can be exported as a GIF.

![Demo](demo/Demo.png)

## Requirements

- Python 3.10+
- `pip install -r requirements.txt` (numpy, matplotlib, Pillow)

## Run

Download `PID.exe` from Releases, or from source:

```
py -3 PIDTeachingAid_GUI.py
```

## How to use

- **PID tab**: drag Kp / Ki / Kd or nudge them with the -/+ buttons (1 % of
  the range per click). The charts, the metrics and the parameter card
  redraw on every change.
- **Plant tab**: the mass-spring-damper values, m = 1, c = 0.5, k = 2.
- **Play / Pause / Stop** run the response animation; **Export** saves it as
  a GIF with a parameter card.
- Gains and the mode are saved to `%TEMP%\PIDTeachingAid.txt` and restored
  on the next launch.

## Project layout

| File | Purpose |
| --- | --- |
| `PIDTeachingAid_GUI.py` | Main window and application state |
| `simulation.py` | Pure computation: PID simulation and metrics (no GUI) |
| `plotPanel.py` | Response / control-force charts |
| `animPanel.py` | Spring-mass animation and the GIF exporter |
| `boxBase.py` | Reusable widgets (SliderBox, ToolTip) |
| `functions.py` | Small helpers (fonts, resource paths) |
| `tests/` | Automated tests (simulation, DPI regression, test-mode GUI) and a manual smoke script |
| `legacy/` | The original Python 2 versions, kept for reference |

## Test

```
py -3 -m unittest discover tests
```

The GUI smoke test opens a window for a few seconds and prints `SMOKE-OK`:

```
py -3 tests/manual_smoke_gui.py
```

## Pack the exe

PyInstaller is required. Run `make.bat`, or:

```
py -3 -m PyInstaller PID.spec
```

## Updates

- v2.0.0: Python 3.10 rewrite in modules, Plant / PID tabs, Ctrl+F2 test mode (theory overlay, plant sliders, watermark-free export), automated tests.
