#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_COPAW="$ROOT_DIR/.venv/bin/copaw"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/copaw-app.log"
PID_FILE="$LOG_DIR/copaw-app.pid"
HOST="${COPAW_HOST:-127.0.0.1}"
PORT="${COPAW_PORT:-8088}"
START_TIMEOUT="${COPAW_START_TIMEOUT:-180}"

mkdir -p "$LOG_DIR"

if [[ ! -x "$VENV_COPAW" ]]; then
  echo "未找到可执行文件: $VENV_COPAW"
  echo "先在仓库根目录完成安装，再重试。"
  exit 1
fi

get_listen_pid() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

is_running() {
  local pid
  pid="$(get_listen_pid)"
  [[ -n "$pid" ]]
}

show_status() {
  local pid
  pid="$(get_listen_pid)"
  if [[ -n "$pid" ]]; then
    echo "CoPaw 运行中: http://$HOST:$PORT/"
    echo "PID: $pid"
    echo "日志: $LOG_FILE"
  else
    echo "CoPaw 未运行"
  fi
}

start_app() {
  local app_pid
  if is_running; then
    show_status
    return 0
  fi

  export MEMORY_STORE_BACKEND="${MEMORY_STORE_BACKEND:-local}"

  nohup "$VENV_COPAW" app --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
  app_pid=$!
  echo "$app_pid" >"$PID_FILE"

  for ((i = 1; i <= START_TIMEOUT; i++)); do
    if curl -fsS "http://$HOST:$PORT/api/version" >/dev/null 2>&1; then
      echo "CoPaw 已启动: http://$HOST:$PORT/"
      echo "PID: $app_pid"
      echo "日志: $LOG_FILE"
      return 0
    fi

    if ! kill -0 "$app_pid" >/dev/null 2>&1; then
      echo "CoPaw 启动失败，最近日志如下:"
      tail -n 40 "$LOG_FILE" || true
      return 1
    fi

    sleep 1
  done

  echo "等待启动超时，最近日志如下:"
  tail -n 40 "$LOG_FILE" || true
  return 1
}

stop_app() {
  local pid
  pid="$(get_listen_pid)"

  if [[ -z "$pid" && -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  fi

  if [[ -z "$pid" ]]; then
    echo "CoPaw 未运行"
    return 0
  fi

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    rm -f "$PID_FILE"
    echo "PID 文件已过期，CoPaw 当前未运行"
    return 0
  fi

  kill "$pid"

  for ((i = 1; i <= 15; i++)); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      rm -f "$PID_FILE"
      echo "CoPaw 已停止"
      return 0
    fi
    sleep 1
  done

  echo "停止超时，尝试强制结束 PID: $pid"
  kill -9 "$pid"
  rm -f "$PID_FILE"
  echo "CoPaw 已强制停止"
}

show_logs() {
  if [[ ! -f "$LOG_FILE" ]]; then
    echo "日志文件不存在: $LOG_FILE"
    return 1
  fi
  tail -n 80 "$LOG_FILE"
}

show_menu() {
  while true; do
    echo "请选择操作:"
    echo "1) 启动 CoPaw"
    echo "2) 停止 CoPaw"
    echo "3) 查看状态"
    echo "4) 查看日志"
    echo "5) 退出"
    read -r -p "输入编号 [1-5]: " choice

    case "$choice" in
      1) start_app ;;
      2) stop_app ;;
      3) show_status ;;
      4) show_logs ;;
      5) exit 0 ;;
      *)
        echo "无效选择: $choice"
        ;;
    esac

    echo
  done
}

case "${1:-menu}" in
  start)
    start_app
    ;;
  stop)
    stop_app
    ;;
  status)
    show_status
    ;;
  logs)
    show_logs
    ;;
  menu)
    show_menu
    ;;
  *)
    echo "用法: $0 [menu|start|stop|status|logs]"
    exit 1
    ;;
esac
