"""Process-wide test configuration loaded before application imports.

The application no longer embeds usable demo credentials.  Tests opt in to
their isolated bootstrap accounts explicitly so production startup never
inherits test/demo identities.
"""
from __future__ import annotations

import os


os.environ.setdefault("SAT_ENV", "test")
os.environ.setdefault("SAT_SEED_DEMO_USERS", "true")
os.environ.setdefault("SAT_SEED_DEMO_DATA", "true")
os.environ.setdefault("SAT_BOOTSTRAP_ADMIN_PASSWORD", "Admin@SAT2026!")
os.environ.setdefault("SAT_BOOTSTRAP_SUPERVISOR_PASSWORD", "Supervisor@SAT2026!")
os.environ.setdefault("SAT_BOOTSTRAP_ANALYST_PASSWORD", "Analyst@SAT2026!")
