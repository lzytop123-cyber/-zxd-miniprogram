"""Production first-time init: create tables + seed."""

import os
import subprocess
import sys
from pathlib import Path

from app.db.session import Base, engine

ROOT = Path(__file__).resolve().parent.parent


def main():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Running seed...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "seed.py")], cwd=str(ROOT), env=env)
    print()
    print("Production init done. See docs/DEPLOY.md for next steps.")


if __name__ == "__main__":
    main()
