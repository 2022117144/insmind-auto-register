"""
Dreamina Auto Register - Desktop GUI Wrapper
Using pywebview to provide a native window experience.
"""

import os
import sys
import threading
import time
import webview
import uvicorn
import socket
from pathlib import Path

# Fix for PyInstaller relative paths
if getattr(sys, "frozen", False):
    # In PyInstaller bundle, dependencies are in _internal
    # but some data might be searched in _MEIPASS
    pass

import logging

# Configure logging to file (use main app logger only)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def check_environment():
    """Environment sanity check"""
    logging.info(f"CWD: {os.getcwd()}")
    logging.info(f"sys.path: {sys.path}")
    try:
        import fastapi
        import uvicorn
        import webview

        logging.info("Core dependencies imported successfully")
    except Exception as e:
        logging.error(f"Dependency import failed: {e}")
        return False

    # Check for app package
    app_path = Path(__file__).parent / "app"
    if not app_path.exists():
        # In bundled mode, it might be in _internal/app
        app_path = Path(__file__).parent / "_internal" / "app"

    logging.info(f"Estimated app path: {app_path} (exists: {app_path.exists()})")
    return True


def find_free_port():
    """Find a free port on localhost"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            logging.info(f"Found free port: {port}")
            return port
    except Exception as e:
        logging.error(f"Failed to find free port: {e}")
        return 8005  # Fallback


def run_server(port):
    """Run the FastAPI server"""
    logging.info("Server thread started")
    try:
        # Crucial: Ensure the 'app' can be found in sys.path
        base = Path(__file__).parent
        internal = base / "_internal"
        if internal.exists() and str(internal) not in sys.path:
            sys.path.insert(0, str(internal))
            logging.info(f"Added {internal} to sys.path")

        # Pre-flight: Ensure directories exist before app initialization
        from app.core import ensure_directories, settings, BASE_DIR

        env_path = BASE_DIR / ".env"
        logging.info(
            f"Checking for .env at: {env_path.absolute()} (Exists: {env_path.exists()})"
        )
        logging.info(
            f"Settings loaded: clash_controller_url={settings.clash_controller_url}"
        )

        ensure_directories()
        logging.info("Core directories ensured")

        from app.main import app

        logging.info("FastAPI app imported successfully")

        config = uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="debug", loop="auto"
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        logging.exception("Background server crashed")
        print(f"Server Error: {e}")


def is_server_ready(url):
    """Wait for server to respond"""
    import urllib.request

    logging.info(f"Checking if server is ready at {url}...")
    for i in range(30):  # Try for 15 seconds
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    logging.info("Server is ready!")
                    return True
        except Exception as e:
            if i % 10 == 0:
                logging.debug(f"Waiting for server... ({e})")
            time.sleep(0.5)
    return False


def main():
    logging.info("--- Application Starting ---")
    try:
        if not check_environment():
            print("Environment check failed. See gui_error.log for details.")

        # 1. Find a free port
        port = find_free_port()
        url = f"http://127.0.0.1:{port}"

        # 2. Start backend in a daemon thread
        server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
        server_thread.start()

        # 3. Wait for server to start
        print(f"Starting background services on {url}...")
        if not is_server_ready(url):
            logging.error(
                "Server failed to respond in time. Continuing to launch window anyway."
            )

        # 4. Create and start the native window
        logging.info("Creating webview window")
        window = webview.create_window(
            "Dreamina Auto Register v2.0",
            url,
            width=1280,
            height=850,
            min_size=(1024, 768),
            background_color="#0f172a",
        )

        logging.info("Starting webview loop")
        webview.start(debug=False)
    except Exception as e:
        logging.exception("GUI Main process crashed")
        print(f"Fatal Error: {e}")


if __name__ == "__main__":
    main()
