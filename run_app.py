"""
SAT-SA One-Click Application Runner.
Starts the FastAPI backend and serves the interactive supervisory dashboard on port 8000.
"""
import os
import sys
import webbrowser
from pathlib import Path

# Ensure SAT-SA root is in Python path and current working directory
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

def main():
    print("=" * 70)
    print(" SAT-SA: Supervisory Analytics Tool for SOC Assessment")
    print(" SIH Problem Statement 26157 • Air-Gapped NCIIPC Examiner Edition")
    print("=" * 70)
    print("\n[+] Starting FastAPI backend with unified React dashboard on http://127.0.0.1:8000 ...")
    
    # Try opening browser after a brief moment
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    main()
