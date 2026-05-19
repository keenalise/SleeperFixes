# 👁️ Eye Blink Tab Switcher

A hands-free browser tab switcher for Linux that uses your webcam to detect deliberate eye blinks and fires a keyboard shortcut — no hands required.

Built with **MediaPipe Face Mesh** for landmark detection and **OpenCV** for the camera feed and visual HUD.

---

## How It Works

The script reads frames from your webcam and uses MediaPipe's Face Mesh to locate 6 landmarks around each eye. From those points it computes the **Eye Aspect Ratio (EAR)**:

```
EAR = (‖p2−p6‖ + ‖p3−p5‖) / (2 · ‖p1−p4‖)
```

- Open eye → EAR ≈ 0.25–0.35  
- Closed eye → EAR ≈ 0.10–0.18

When both eyes stay below the threshold for a set number of consecutive frames (a deliberate blink, not a natural one), it fires a configurable keyboard shortcut to your browser.

---

## Requirements

- **Ubuntu** (tested on Ubuntu with X11)
- **Python 3.12**
- **xdotool** — for window focus and key injection on X11

### System dependencies

```bash
sudo apt install xdotool
```

### Python dependencies

```
opencv-python>=4.8,<4.12
mediapipe==0.10.21
```

---

## Setup

**1. Clone / download the project and enter the directory**

```bash
cd eyetracking
```

**2. Create a virtual environment**

```bash
python3 -m venv .venv
```

**3. Activate the virtual environment**

```bash
source .venv/bin/activate
```

Your terminal prompt should now show `(.venv)` at the start.

**4. Install Python dependencies**

```bash
pip install -r requirements.txt
```

---

## Usage

Make sure the virtual environment is active first (`source .venv/bin/activate`), then:

```bash
python eyetracking.py
```

Or, without activating the venv, you can run it directly via:

```bash
.venv/bin/python eyetracking.py
```

Or use the provided launch script (handles environment setup automatically):

```bash
./run.sh
```

A camera preview window will open showing:
- Live eye outline overlays (green = open, red = closed)
- EAR values and threshold in a HUD overlay
- A `>>> CTRL+1 SENT <<<` flash when the shortcut fires

Press **`Q`** in the preview window to quit.

### Full example from scratch (every command in order)

```bash
cd eyetracking
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python eyetracking.py
```

After the first-time setup, next time you just need:

```bash
cd eyetracking
source .venv/bin/activate
python eyetracking.py
```

---

## Configuration

All tunable settings are at the top of `eyetracking.py`:

| Variable | Default | Description |
|---|---|---|
| `EAR_THRESHOLD` | `0.20` | EAR value below which an eye is considered closed. Lower = less sensitive; raise if squints trigger it accidentally. |
| `CLOSED_FRAME_THRESHOLD` | `4` | Consecutive frames both eyes must be closed before the shortcut fires (~130 ms at 30 fps). Raise to avoid accidental triggers. |
| `HOTKEY` | `('ctrl', '1')` | Keyboard shortcut to send. Examples: `('ctrl', '2')`, `('ctrl', 't')`. |
| `BROWSER_WINDOW_MATCH` | `'Brave'` | Substring matched against the window title to focus before sending the hotkey. Change to `'Firefox'`, `'Chrome'`, etc. |
| `CAMERA_INDEX` | `0` | Webcam index. Try `1` or `2` for external cameras. |
| `DEBOUNCE_SECONDS` | `1.5` | Cooldown after a shortcut fires. Prevents repeated triggers if you hold your eyes shut. |

---

## File Structure

```
eyetracking/
├── eyetracking.py        # Main script
├── requirements.txt      # Python dependencies
├── run.sh                # Launch script (handles Wayland auth + ydotoold check)
├── start-ydotoold.sh     # One-time daemon starter for ydotool (Wayland key injection)
├── .venv/                # Python virtual environment
└── .vscode/
    └── settings.json
```

---

## Troubleshooting

**Hotkey doesn't reach the browser**  
Make sure `xdotool` is installed (`sudo apt install xdotool`) and that the `BROWSER_WINDOW_MATCH` value in `eyetracking.py` matches your browser's window title (e.g. `'Brave'`, `'Firefox'`, `'Chrome'`).

**Blinks aren't detected / trigger too easily**  
Adjust `EAR_THRESHOLD` up or down in small increments (e.g. 0.02 steps). Also try adjusting `CLOSED_FRAME_THRESHOLD`.

**Wrong camera opens**  
Change `CAMERA_INDEX` to `1` or `2`.

**`Cannot open camera` error**  
Make sure no other application is holding the camera device open.

**`ModuleNotFoundError` when running the script**  
You likely forgot to activate the virtual environment. Run `source .venv/bin/activate` first, then try again.

**`mediapipe` install fails**  
Make sure you're on Python 3.12 and using the venv pip: `pip install -r requirements.txt` (after activating).

---

## Conclusion
It is a fun project. ✌️

