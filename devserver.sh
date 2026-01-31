#!/bin/bash
# 1. Aseguramos la activación (sin errores de ortografía)
source .venv/bin/activate

# 2. Ejecutamos con autoridad. Si $PORT no existe, usa el 5000
python -m flask --app app run --port ${PORT:-5000} --debug