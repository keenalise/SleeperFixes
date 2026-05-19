
import cv2
import mediapipe as mp
import glob
import os
import subprocess
import time
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# ██  CONFIGURATION  ──  Tweak these to suit your face, lighting, and needs
# ─────────────────────────────────────────────────────────────────────────────

# Eye Aspect Ratio threshold.
#   EAR > EAR_THRESHOLD  →  eye is OPEN
#   EAR ≤ EAR_THRESHOLD  →  eye is CLOSED
#
#   Typical open-eye EAR is ~0.25–0.35.
#   Typical closed-eye EAR is ~0.10–0.18.
#   Start with 0.20 and adjust: if the script misses blinks, lower it;
#   if it triggers on squints, raise it.
EAR_THRESHOLD = 0.20

# How many consecutive frames both eyes must be below EAR_THRESHOLD
# before the shortcut fires.  3–5 frames ≈ 100–165 ms at 30 fps.
# Raise to avoid accidental triggers; lower for faster response.
CLOSED_FRAME_THRESHOLD = 4

# The keyboard shortcut to send when a deliberate blink is detected.
# Examples:
#   ('ctrl', '1')  →  Ctrl+1  (first pinned tab in most browsers)
#   ('ctrl', '2')  →  Ctrl+2
#   ('ctrl', 't')  →  open new tab
HOTKEY = ('ctrl', '1')

# Substring matched against window title / WM class before sending the hotkey.
# Brave on Wayland is invisible to xdotool — we focus it via GNOME Shell instead.
BROWSER_WINDOW_MATCH = 'Brave'

# Webcam device index.  0 = default camera; try 1, 2, … for external cams.
CAMERA_INDEX = 0

# After firing the shortcut, ignore further closures for this many seconds.
# Prevents repeated triggers if you hold your eyes shut.
DEBOUNCE_SECONDS = 1.5

def ensure_x11_auth():
    """
    Cursor's integrated terminal often has DISPLAY=:0 but no XAUTHORITY.
    On GNOME/Wayland the cookie lives in /run/user/<uid>/.mutter-Xwaylandauth.*
    """
    if os.environ.get("XAUTHORITY") and os.path.exists(os.environ["XAUTHORITY"]):
        return
    for path in glob.glob(f"/run/user/{os.getuid()}/.mutter-Xwaylandauth.*"):
        os.environ["XAUTHORITY"] = path
        return


# Linux input-event-codes.h keycodes for ydotool
_YDOTOOL_KEYCODES = {
    'ctrl': 29, 'control': 29, 'shift': 42, 'alt': 56, 'super': 125, 'meta': 125,
    'tab': 15, 't': 20,
    **{str(d): c for d, c in zip(range(10), range(2, 12))},
}

_MODIFIERS = frozenset({'ctrl', 'control', 'shift', 'alt', 'super', 'meta'})


def _ydotool_socket():
    sock = os.environ.get('YDOTOOL_SOCKET')
    if sock and os.path.exists(sock):
        return sock
    default = f'/run/user/{os.getuid()}/.ydotool_socket'
    return default if os.path.exists(default) else None


def focus_browser(match=BROWSER_WINDOW_MATCH):
    """Simple X11 focus using xdotool."""
    # Search for the window ID
    search = subprocess.run(
        ['xdotool', 'search', '--name', match],
        capture_output=True, text=True
    )
    if search.returncode == 0 and search.stdout.strip():
        # Get the last window ID found
        wid = search.stdout.strip().splitlines()[-1]
        # Activate (focus) that window
        subprocess.run(['xdotool', 'windowactivate', '--sync', wid])
        return True
    return False

def send_hotkey(keys):
    """Simple X11 hotkey injection."""
    if focus_browser():
        time.sleep(0.1) # Small delay to ensure focus took hold
        # xdotool key format is 'ctrl+1'
        key_combo = '+'.join(keys)
        subprocess.run(['xdotool', 'key', key_combo])
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# ██  MEDIAPIPE FACE MESH EYE LANDMARK INDICES
#
#   MediaPipe Face Mesh provides 468 landmarks.  We pick the six points that
#   outline each eye, matching the standard EAR formula.
#
#   Left eye  (from camera's point of view = YOUR right eye):
LEFT_EYE_INDICES  = [362, 385, 387, 263, 373, 380]
#   Right eye (from camera's point of view = YOUR left eye):
RIGHT_EYE_INDICES = [33,  160, 158, 133, 153, 144]
# ─────────────────────────────────────────────────────────────────────────────


def eye_aspect_ratio(landmarks, eye_indices, image_w, image_h):
    """
    Compute the Eye Aspect Ratio (EAR) for a single eye.

    The EAR is defined as:
        EAR = (‖p2−p6‖ + ‖p3−p5‖) / (2 · ‖p1−p4‖)

    where p1…p6 are the six eye-outline landmarks in order:
        p1 = outer corner
        p2 = upper-outer
        p3 = upper-inner
        p4 = inner corner
        p5 = lower-inner
        p6 = lower-outer

    A fully open eye gives EAR ≈ 0.25–0.35.
    A closed eye gives EAR ≈ 0.0–0.18.

    Args:
        landmarks   : the normalized landmark list from MediaPipe
        eye_indices : list of 6 landmark indices for this eye
        image_w     : frame pixel width  (to de-normalise x)
        image_h     : frame pixel height (to de-normalise y)

    Returns:
        float: the EAR value
    """
    # Extract (x, y) pixel coordinates for each of the 6 landmarks
    pts = []
    for idx in eye_indices:
        lm = landmarks[idx]
        pts.append(np.array([lm.x * image_w, lm.y * image_h]))

    p1, p2, p3, p4, p5, p6 = pts

    # Vertical distances (numerator)
    vert_a = np.linalg.norm(p2 - p6)
    vert_b = np.linalg.norm(p3 - p5)

    # Horizontal distance (denominator)
    horiz  = np.linalg.norm(p1 - p4)

    if horiz == 0:          # Guard against degenerate frames
        return 0.0

    return (vert_a + vert_b) / (2.0 * horiz)


def draw_eye_outline(frame, landmarks, eye_indices, image_w, image_h, color):
    """Draw a polygon around an eye for visual feedback."""
    pts = []
    for idx in eye_indices:
        lm = landmarks[idx]
        pts.append((int(lm.x * image_w), int(lm.y * image_h)))
    pts = np.array(pts, dtype=np.int32)
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=1)


def draw_hud(frame, ear_left, ear_right, avg_ear, eyes_closed, closed_frames,
             shortcut_fired):
    """
    Render a debug HUD onto the frame showing EAR values and eye state.
    """
    h, w = frame.shape[:2]

    # ── Semi-transparent black banner at the top ──────────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 110), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    # ── EAR readouts ──────────────────────────────────────────────────────
    cv2.putText(frame, f"EAR  L: {ear_left:.3f}   R: {ear_right:.3f}   AVG: {avg_ear:.3f}",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    cv2.putText(frame, f"Threshold: {EAR_THRESHOLD:.2f}   Closed frames: {closed_frames}/{CLOSED_FRAME_THRESHOLD}",
                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    # ── Eye state label ───────────────────────────────────────────────────
    if eyes_closed:
        state_text  = "EYES: CLOSED"
        state_color = (50, 50, 255)     # red-ish
    else:
        state_text  = "EYES: OPEN"
        state_color = (50, 220, 50)     # green

    cv2.putText(frame, state_text, (10, 82),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, state_color, 2)

    # ── Shortcut flash ────────────────────────────────────────────────────
    if shortcut_fired:
        hotkey_str = "+".join(k.upper() for k in HOTKEY)
        cv2.putText(frame, f">>> {hotkey_str} SENT <<<",
                    (w // 2 - 90, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)

    # ── Quit hint ─────────────────────────────────────────────────────────
    cv2.putText(frame, "Press Q to quit",
                (w - 155, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)


# ─────────────────────────────────────────────────────────────────────────────
# ██  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Eye Blink Tab Switcher — starting up …")
    print(f"  EAR threshold     : {EAR_THRESHOLD}")
    print(f"  Closed frames req : {CLOSED_FRAME_THRESHOLD}")
    print(f"  Hotkey            : {'+'.join(k.upper() for k in HOTKEY)}")
    print(f"  Browser match     : {BROWSER_WINDOW_MATCH}")
    print(f"  Debounce          : {DEBOUNCE_SECONDS}s")
    if not _ydotool_socket():
        print("  WARNING: ydotoold not running — use ./run.sh or start ydotoold")
    print("=" * 60)
    print("  Press  Q  in the camera window to quit.\n")

    # ── Initialise MediaPipe Face Mesh ────────────────────────────────────
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,            # We only need the user's face
        refine_landmarks=True,      # Enables the iris/eye-detail landmarks
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )

    # ── Open webcam ───────────────────────────────────────────────────────
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera index {CAMERA_INDEX}. "
            "Try changing CAMERA_INDEX to 1 or 2."
        )

    # ── State variables ───────────────────────────────────────────────────
    closed_frame_count = 0          # Consecutive frames where eyes were closed
    shortcut_fired     = False      # True if shortcut was fired this closure
    last_fire_time     = 0.0        # Timestamp of the last shortcut fire
    flash_until        = 0.0        # Show "SENT" overlay until this timestamp

    # ── Main loop ─────────────────────────────────────────────────────────
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Warning: failed to grab frame — retrying …")
            time.sleep(0.05)
            continue

        # Mirror the frame so it feels like a selfie-camera
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        # Convert BGR → RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results   = face_mesh.process(rgb_frame)

        ear_left  = 0.0
        ear_right = 0.0
        avg_ear   = 0.0
        eyes_closed = False

        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark

            # ── Compute EAR for both eyes ─────────────────────────────────
            ear_left  = eye_aspect_ratio(landmarks, LEFT_EYE_INDICES,  w, h)
            ear_right = eye_aspect_ratio(landmarks, RIGHT_EYE_INDICES, w, h)
            avg_ear   = (ear_left + ear_right) / 2.0

            # ── Draw eye outlines (green=open, red=closed) ────────────────
            left_closed  = ear_left  <= EAR_THRESHOLD
            right_closed = ear_right <= EAR_THRESHOLD
            left_color   = (50, 50, 255) if left_closed  else (50, 220, 50)
            right_color  = (50, 50, 255) if right_closed else (50, 220, 50)
            draw_eye_outline(frame, landmarks, LEFT_EYE_INDICES,  w, h, left_color)
            draw_eye_outline(frame, landmarks, RIGHT_EYE_INDICES, w, h, right_color)

            # ── Decide whether both eyes are closed ───────────────────────
            eyes_closed = left_closed and right_closed

        # ── Frame counter & debounce logic ────────────────────────────────
        if eyes_closed:
            closed_frame_count += 1
        else:
            # Eyes opened again — reset counter and arm for next closure
            closed_frame_count = 0
            shortcut_fired     = False

        # ── Trigger shortcut exactly once per closure event ───────────────
        now = time.time()
        if (closed_frame_count >= CLOSED_FRAME_THRESHOLD
                and not shortcut_fired
                and (now - last_fire_time) >= DEBOUNCE_SECONDS):

            print(f"[{time.strftime('%H:%M:%S')}]  Blink detected "
                  f"(EAR={avg_ear:.3f})  →  firing "
                  f"{'+'.join(k.upper() for k in HOTKEY)}")

            send_hotkey(HOTKEY)

            shortcut_fired = True
            last_fire_time = now
            flash_until    = now + 0.8   # Show the flash overlay for 0.8 s

        # ── Render HUD ────────────────────────────────────────────────────
        show_flash = (now < flash_until)
        draw_hud(frame, ear_left, ear_right, avg_ear,
                 eyes_closed, closed_frame_count, show_flash)

        # ── Display ───────────────────────────────────────────────────────
        cv2.imshow("Eye Blink Monitor  (Q to quit)", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\nQ pressed — shutting down.")
            break

    # ── Cleanup ───────────────────────────────────────────────────────────
    cap.release()
    face_mesh.close()
    cv2.destroyAllWindows()
    print("Goodbye!")


if __name__ == "__main__":
    main()