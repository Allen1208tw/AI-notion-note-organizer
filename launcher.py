from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


from src.config.runtime_paths import OUTPUT_DIR, RESOURCE_DIR, is_frozen_application


PROJECT_DIR = RESOURCE_DIR
APP_FILE = PROJECT_DIR / "AI_Notion_筆記整理器.py"
BACKGROUND_WORKER_FILE = PROJECT_DIR / "background_worker.py"
SERVER_STATE_FILE = OUTPUT_DIR / ".streamlit_server.json"
REQUIRED_MODULES = {
    "streamlit": "streamlit",
    "sqlalchemy": "sqlalchemy",
    "pandas": "pandas",
    "requests": "requests",
    "fitz": "pymupdf",
    "docx": "python-docx",
    "dotenv": "python-dotenv",
    "pydantic": "pydantic",
    "notion_client": "notion-client",
    "openai": "openai",
}


def _port_is_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def _find_available_port(start: int = 8501, attempts: int = 50) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue

    raise RuntimeError("找不到可用的本機連接埠。")


def _load_running_server() -> int | None:
    if not SERVER_STATE_FILE.exists():
        return None

    try:
        state = json.loads(SERVER_STATE_FILE.read_text(encoding="utf-8"))
        port = int(state.get("port", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        port = 0

    if port > 0 and _port_is_open(port):
        return port

    try:
        SERVER_STATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    return None


def _check_environment() -> list[str]:
    errors: list[str] = []

    if not APP_FILE.exists():
        errors.append(f"找不到主程式：{APP_FILE.name}")

    if not BACKGROUND_WORKER_FILE.exists():
        errors.append(f"找不到背景 Worker：{BACKGROUND_WORKER_FILE.name}")

    missing_packages = [
        package_name
        for module_name, package_name in REQUIRED_MODULES.items()
        if importlib.util.find_spec(module_name) is None
    ]

    if missing_packages:
        errors.append(
            "缺少套件："
            + ", ".join(missing_packages)
            + "。請執行 pip install -r requirements.txt"
        )

    if not errors:
        try:
            from src.database.init_db import initialize_database

            errors.extend(initialize_database())
        except Exception as error:
            errors.append(f"資料庫初始化失敗：{error}")

    return errors


def _run_streamlit_server(port: int) -> int:
    sys.argv = [
        "streamlit",
        "run",
        str(APP_FILE),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--global.developmentMode",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    from streamlit.web.cli import main as streamlit_main

    result = streamlit_main()
    return int(result or 0)


def _worker_command() -> list[str]:
    if is_frozen_application():
        return [sys.executable, "--background-worker", "--poll-seconds", "1"]
    return [sys.executable, str(BACKGROUND_WORKER_FILE), "--poll-seconds", "1"]


def _streamlit_command(port: int) -> list[str]:
    if is_frozen_application():
        return [sys.executable, "--streamlit-server", "--port", str(port)]
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_FILE),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--global.developmentMode",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]


def _check_for_updates_in_background() -> None:
    try:
        from src.services.update_service import check_and_cache_update

        check_and_cache_update()
    except Exception as error:
        print(f"自動更新檢查略過：{error}")


def _wait_for_server(port: int, process: subprocess.Popen, timeout: float = 20) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        if _port_is_open(port):
            return True
        time.sleep(0.2)

    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Notion 筆記整理器啟動器")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只檢查環境與資料庫，不啟動網頁",
    )
    parser.add_argument("--background-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--streamlit-server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8501, help=argparse.SUPPRESS)
    parser.add_argument("--poll-seconds", type=float, default=1.0, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.background_worker:
        from background_worker import run_worker

        return run_worker(poll_seconds=args.poll_seconds)

    if args.streamlit_server:
        return _run_streamlit_server(args.port)

    os.chdir(PROJECT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    errors = _check_environment()

    if errors:
        print("啟動前檢查失敗：")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.check:
        print("啟動環境、必要套件與 SQLite Schema 均正常。")
        return 0

    running_port = _load_running_server()
    if running_port:
        url = f"http://127.0.0.1:{running_port}"
        print(f"應用程式已在執行：{url}")
        webbrowser.open(url)
        return 0

    port = _find_available_port()
    url = f"http://127.0.0.1:{port}"
    command = _streamlit_command(port)

    print("正在啟動 AI Notion 筆記整理器...")
    worker_process = subprocess.Popen(_worker_command(), cwd=PROJECT_DIR)
    process = subprocess.Popen(command, cwd=PROJECT_DIR)

    try:
        if not _wait_for_server(port, process):
            print("Streamlit 啟動失敗，請查看上方錯誤訊息。")
            return process.poll() or 1

        SERVER_STATE_FILE.write_text(
            json.dumps(
                {"pid": process.pid, "port": port},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"應用程式已開啟：{url}")
        print("背景工作 Worker 已啟動。")
        print("保持這個視窗開啟；關閉視窗即可停止應用程式與 Worker。")
        webbrowser.open(url)
        threading.Thread(
            target=_check_for_updates_in_background,
            daemon=True,
        ).start()
        return process.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        if worker_process.poll() is None:
            worker_process.terminate()
            try:
                worker_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker_process.kill()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            SERVER_STATE_FILE.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
