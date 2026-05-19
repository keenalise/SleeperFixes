#!/usr/bin/env bash
cd "$(dirname "$0")"

# GNOME on Wayland: X11 apps need the Mutter XWayland auth cookie.
if [[ -z "${XAUTHORITY:-}" || ! -f "${XAUTHORITY}" ]]; then
  cookie=$(ls /run/user/"$(id -u)"/.mutter-Xwaylandauth.* 2>/dev/null | head -1)
  if [[ -n "$cookie" ]]; then
    export XAUTHORITY="$cookie"
  fi
fi

# ydotool sends keys on Wayland (Brave is not reachable via xdotool).
export YDOTOOL_SOCKET="${YDOTOOL_SOCKET:-/run/user/$(id -u)/.ydotool_socket}"
if [[ ! -S "$YDOTOOL_SOCKET" ]]; then
  if command -v ydotoold &>/dev/null; then
    echo "Starting ydotoold (needs sudo password once per boot) …"
    sudo ydotoold --socket-path="$YDOTOOL_SOCKET" --socket-own="$(id -u):$(id -g)" &
    sleep 0.5
  fi
  if [[ ! -S "$YDOTOOL_SOCKET" ]]; then
    echo "WARNING: ydotoold is not running — hotkeys may not reach Brave on Wayland."
    echo "  Start it manually:  sudo ydotoold --socket-path=\"\$YDOTOOL_SOCKET\" --socket-own=\"\$(id -u):\$(id -g)\" &"
    echo
  fi
fi

exec .venv/bin/python eyetracking.py "$@"
