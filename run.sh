#!/usr/bin/env bash
# run.sh — Arranque de AuditMayorista
#   ./run.sh            interfaz Streamlit
#   ./run.sh audit      auditoría automatizada
#   ./run.sh report     informes
#   ./run.sh demo       demostración con DATOS SIMULADOS
#   ./run.sh test       pruebas
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
command -v python3 >/dev/null || { echo "Se requiere Python 3.10 o superior"; exit 1; }
case "${1:-web}" in
  web)    python3 -m streamlit run app.py ;;
  audit)  python3 main.py audit "${@:2}" ;;
  report) python3 main.py report "${@:2}" ;;
  demo)   python3 main.py demo ;;
  test)   python3 -m pytest -q ;;
  *)      echo "Uso: ./run.sh [web|audit|report|demo|test]"; exit 1 ;;
esac
