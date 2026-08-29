import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

scripts = [
    PROJECT_ROOT / "scripts" / "download_kraken_data.py",
    PROJECT_ROOT / "scripts" / "import_kraken_data.py",
]

print("=" * 50)
print("KRAKEN DATA UPDATE")
print("=" * 50)

for script in scripts:
    print(f"\nRunning {script.name}...")

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=PROJECT_ROOT
    )

    if result.returncode != 0:
        print(f"\nERROR: {script.name} failed.")
        sys.exit(result.returncode)

print("\n" + "=" * 50)
print("UPDATE COMPLETE")
print("=" * 50)