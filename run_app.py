"""
SAT-SA One-Click Application Runner.
Starts the FastAPI backend and serves the interactive supervisory dashboard on port 8000.
"""
import sys
import webbrowser
from pathlib import Path
import subprocess

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
