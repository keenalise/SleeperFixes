#!/usr/bin/env bash
# Start ydotoold for Wayland keyboard injection.
# Do NOT use "&" with sudo — enter your password in this terminal, then leave it open.

SOCKET="/run/user/$(id -u)/.ydotool_socket"

if [[ -S "$SOCKET" ]]; then
  echo "ydotoold already running: $SOCKET"
  exit 0
fi

echo "Starting ydotoold (sudo password required) …"
echo "Leave this terminal open while using the eye tracker."
echo

exec sudo ydotoold \
  --socket-path="$SOCKET" \
  --socket-own="$(id -u):$(id -g)"
