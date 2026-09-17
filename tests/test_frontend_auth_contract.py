"""Source-level regression checks for the browser authentication boundary.

The project has no frontend unit-test runner yet; these checks protect the
security contract while TypeScript build verification covers compilation.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_never_contains_default_admin_credentials_or_auto_login():
    api_source = (ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")
    assert "Admin@SAT2026!" not in api_source
    assert "ensureAuthenticated" not in api_source
    assert "localStorage." not in api_source
    assert "login(username: string, password: string)" in api_source


def test_frontend_has_an_explicit_login_view_before_command_center_access():
    app_source = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "LoginView" in app_source
    assert "if (!authenticated) return <LoginView" in app_source
