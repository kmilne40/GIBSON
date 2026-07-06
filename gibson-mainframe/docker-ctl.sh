#!/usr/bin/env bash
# Simple start/stop wrapper around docker compose for gibson-mainframe.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

COMPOSE=(docker compose)
ACTION="${1:-status}"
shift || true

usage() {
  cat <<USAGE
Usage: $0 {start|stop|restart|status|logs} [extra docker compose args]

  start    docker compose up -d --build
  stop     docker compose down
  restart  stop then start
  status   docker compose ps
  logs     docker compose logs -f (Ctrl-C to exit)
USAGE
}

case "$ACTION" in
  start)
    "${COMPOSE[@]}" up -d --build "$@"
    "${COMPOSE[@]}" ps
    ;;
  stop)
    "${COMPOSE[@]}" down "$@"
    ;;
  restart)
    "${COMPOSE[@]}" down "$@"
    "${COMPOSE[@]}" up -d --build "$@"
    "${COMPOSE[@]}" ps
    ;;
  status)
    "${COMPOSE[@]}" ps
    ;;
  logs)
    "${COMPOSE[@]}" logs -f "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
