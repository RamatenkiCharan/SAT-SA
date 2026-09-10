import os
import socket
import sys
import webbrowser
from pathlib import Path

# Ensure SAT-SA root is in Python path and current working directory
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)


def is_port_in_use(port: int = 8000, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def main():
    print("=" * 70)
    print(" SAT-SA: Supervisory Analytics Tool for SOC Assessment")
    print(" SIH Problem Statement 26157 • Air-Gapped NCIIPC Examiner Edition")
    print("=" * 70)

    if is_port_in_use(8000):
        print("\n[+] SAT-SA server is ALREADY RUNNING on http://127.0.0.1:8000")
        print("[+] Opening your browser now...")
        webbrowser.open("http://127.0.0.1:8000")
        print("[+] If you wish to restart the server, close the existing terminal/process running on port 8000.")
        return

    print("\n[+] Starting FastAPI backend with unified React dashboard on http://127.0.0.1:8000 ...")

    # Try opening browser after starting
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
