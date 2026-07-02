from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    ui_path = Path(__file__).resolve().parent / "ui.py"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ui_path),
            "--server.headless=true",
            "--server.address=0.0.0.0",
            "--server.port=8501",
            "--browser.gatherUsageStats=false",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
