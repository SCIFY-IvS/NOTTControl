# NOTTControl

High-level control software for the **NOTT** instrument: a PyQt5 desktop application that talks to instrument hardware over **OPC UA**, logs telemetry to **Redis**, and provides subsystems for delay lines, shutters, tip/tilt, and the science camera.

## Features

- **Main dashboard** for launching instrument sub-windows and monitoring status
- **Delay lines** motor control and saved position presets (Redis)
- **Shutters** and **tip/tilt** interfaces
- **Camera** UI (Infratec / acquisition pipeline, ROI tools, pyqtgraph)
- **OPC UA** client (`asyncua`) and optional **Redis** time series for temperatures, positions, and camera metadata

## Requirements

- **Python 3.10+**
- Network access to the configured **OPC UA** server and (if used) **Redis**

Core dependencies are listed in [`pyproject.toml`](pyproject.toml) (PyQt5, asyncua, numpy, scipy, OpenCV, redis, pyzmq, sympy, matplotlib, pyqtgraph).

Some code paths use **additional** packages that are not declared in `pyproject.toml` today, for example **Astropy** (`nottcontrol/config.py`, alignment / lucid utilities), **pyserial** (piezo hardware), **scikit-learn** (calibration scripts), or **lmfit** (lucid utilities). Install these only if you use those modules.

## Installation

From the repository root:

```bash
pip install .
```

For day-to-day work on a checkout (editable install, picks up code changes without reinstalling):

```bash
pip install -e .
```

Run the application from an environment where the package is installed. The entry script changes the working directory to the `nottcontrol` package folder so that **`config.ini`** and **`.ui`** files are found next to [`nottcontrol/main.py`](nottcontrol/main.py).

## Configuration

Edit [`nottcontrol/config.ini`](nottcontrol/config.ini) for your site:

- **`[DEFAULT]`** `opcuaaddress`, `databaseurl` (Redis), frame directories
- Sections for delay lines, piezo/tip-tilt, camera, and other subsystems

Alignment and script helpers may read additional config under `nottcontrol/script/` and `nottcontrol/lucid/cfg/` depending on the feature you use.

## Running the GUI

After installation:

```bash
python -m nottcontrol.main
```

Alternatively, from the `nottcontrol` directory (so relative paths resolve as in development):

```bash
cd nottcontrol
python main.py
```

The main window expects a reachable OPC UA server at startup.

## Optional: Lucid Arena SDK

Visible-camera / Arena-based tooling (for example in `nottcontrol/lucid/`) expects the vendor **Arena** Python package. Install it separately from Lucid’s distribution hub:

https://thinklucid.com/downloads-hub/

If Arena is not installed, avoid importing or running modules that require `arena_api` until the SDK is available.

## Repository layout (short)

| Path | Role |
|------|------|
| `nottcontrol/main.py` | Application entry |
| `nottcontrol/scifygui.py` | Main window and subsystem dialogs |
| `nottcontrol/components/` | Motors, shutters, piezo, OPC UA helpers |
| `nottcontrol/camera/` | Camera UI and drivers |
| `nottcontrol/commands/` | Motor / camera command abstractions |
| `nottcontrol/script/` | Acquisition, calibration, cophasing scripts and libraries |

## Contributing

Use branches and pull requests against the upstream repository. Keep `config.ini` free of site-specific secrets when committing; prefer local overrides or environment-specific copies where appropriate.
