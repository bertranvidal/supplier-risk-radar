#!/bin/bash
# Trains one text model and one link model, calibrates thresholds and runs the independent holdout.
# Run from anywhere: the script moves to its own folder.
set -e
cd "$(dirname "$0")"

echo "=== Training text model ==="
python3 train_text.py --epochs 3 --bs 8

echo "=== Training link model ==="
python3 train_link.py --epochs 2 --bs 8

echo "=== Calibrating thresholds ==="
python3 calibrate.py

echo "=== Independent holdout (30 articles written by the team) ==="
python3 evaluate.py --data holdout

echo "=== DONE ==="
