#!/bin/sh
set -e
case "${MODE:-api}" in
  api)  exec uvicorn app.server:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --proxy-headers ;;
  bot)  exec python -m app.telegram_bot ;;
  all)  python -m app.telegram_bot &
        exec uvicorn app.server:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --proxy-headers ;;
  *)    echo "MODE must be api|bot|all"; exit 1 ;;
esac
