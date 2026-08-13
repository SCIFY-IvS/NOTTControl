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

Core dependencies are listed in [`pyproject.toml`](pyproject.toml) (PyQt5, asyncua, numpy, scipy, OpenCV headless, redis, pyzmq, sympy, matplotlib, pyqtgraph).

Some code paths use **additional** packages that are not declared in `pyproject.toml` today, for example **Astropy** (`nottcontrol/config.py`, alignment / lucid utilities), **pyserial** (piezo hardware), **scikit-learn** (calibration scripts), or **lmfit** (lucid utilities). Install these only if you use those modules.

## Installation

From the repository root (use the same `python` / conda env you will run the GUI with):

```bash
python -m pip install -e .
```

Non-editable install:

```bash
python -m pip install .
```

In a conda environment you can also use (requires `conda-build` / `conda install conda-build`):

```bash
conda develop .
```

**OpenCV:** the default dependency is `opencv-python-headless` (no bundled Qt). Do **not** install `opencv-python` or `opencv-contrib-python` alongside PyQt5 — their Qt plugins break the GUI on Linux (`Could not load the Qt platform plugin "xcb" .../cv2/qt/plugins`).

If an older env already has the full OpenCV build:

```bash
python -m pip uninstall -y opencv-contrib-python opencv-python
python -m pip install opencv-python-headless
unset QT_QPA_PLATFORM_PLUGIN_PATH QT_PLUGIN_PATH
```

### Linux (nott-server) notes

```bash
cd /path/to/NOTTControl
python -m pip install -e .
unset QT_QPA_PLATFORM_PLUGIN_PATH QT_PLUGIN_PATH
python -m nottcontrol.main
```

If `xcb` still fails after switching to headless OpenCV, install system Qt/XCB libs (Debian/Ubuntu), for example:

```bash
sudo apt-get install -y libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0
```

**VNC / remote desktop:** PyQt5 and pyqtgraph need OpenGL. Over VNC you often see
`qglx_findConfig: Failed to finding matching FBConfig`. Use software rendering:

```bash
unset QT_QPA_PLATFORM_PLUGIN_PATH QT_PLUGIN_PATH
export LIBGL_ALWAYS_SOFTWARE=1
export QT_OPENGL=software
export QT_X11_NO_MITSHM=1
python -m nottcontrol.main
```

Optional Mesa packages if GL is missing entirely:

```bash
sudo apt-get install -y libgl1-mesa-dri mesa-utils
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

On **macOS**, use the bundled launcher for the correct Dock/Finder icon instead of the default Python logo:

```bash
open NOTTControl.app
```

You can drag `NOTTControl.app` to the Dock or Applications folder. The app bundle runs `python -m nottcontrol.main` using your project virtual environment (`.venv` / `venv`) when present.

On **Windows**, create or refresh a Desktop shortcut with the NOTT icon (not the default Python logo):

```bat
Create-NOTTControlShortcut.bat
```

Or:

```powershell
powershell -ExecutionPolicy Bypass -File nottcontrol\windows\Create-NOTTControlShortcut.ps1
```

```bash
python -m nottcontrol.main --create-shortcut
```

If an older shortcut still shows the Python icon, delete it and run one of the commands above. Rebuilding assets also refreshes the shortcut:

```bash
python nottcontrol/windows/build_assets.py
```

You can also double-click `NOTTControl.bat` in the repository root. It launches the GUI with `pythonw` and uses the NOTT icon in the taskbar while the app is running.

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
