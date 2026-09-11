"""
SAT-SA One-Click Application Runner.
Starts the FastAPI backend and serves the interactive supervisory dashboard on port 8000.
"""
import sys
import webbrowser
from pathlib import Path
import subprocess

def _ensure_frontend_built() -> None:
    """Build the React frontend if dist/ doesn't exist yet, so the launcher is
    actually one-click instead of silently serving an API with no UI."""
    repo_root = Path(__file__).resolve().parent
    frontend_dir = repo_root / "frontend"
    dist_dir = frontend_dir / "dist"
    if dist_dir.exists():
        return

    print("[+] frontend/dist not found — building the React dashboard first...")
    try:
        subprocess.run(["npm", "install"], cwd=str(frontend_dir), check=True)
        subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)
        print("[+] Frontend build complete.")
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"[!] Could not build frontend automatically ({exc}).")
        print("    Run manually: cd frontend && npm install && npm run build")
        print("    Continuing to start the API-only backend...")


def main():
    print("=" * 70)
    print(" SAT-SA: Supervisory Analytics Tool for SOC Assessment")
    print(" Air-Gapped NCIIPC Examiner Edition")
    print("=" * 70)

    _ensure_frontend_built()

    print("\n[+] Starting FastAPI backend with unified React dashboard on http://127.0.0.1:8000 ...")
    
    # Try opening browser after a brief moment
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
