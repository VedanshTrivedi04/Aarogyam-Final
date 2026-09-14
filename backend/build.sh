#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "================================================="
echo " Building Aarogyam / MedAdhere Backend on Render "
echo "================================================="

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing requirements..."
pip install -r requirements.txt

echo "==> Collecting static assets (WhiteNoise)..."
python manage.py collectstatic --no-input

echo "==> Running non-destructive database migrations..."
python manage.py migrate --no-input

echo "==> Build complete!"
