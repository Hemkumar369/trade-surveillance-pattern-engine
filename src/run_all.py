"""Run the whole pipeline: generate -> reconcile -> detect -> evaluate -> tune."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
for step in ["generate_data.py", "reconcile.py", "patterns.py", "evaluate.py", "tune.py"]:
    print(f"\n===== {step} =====")
    subprocess.run([sys.executable, str(HERE / step)], check=True, cwd=HERE)
