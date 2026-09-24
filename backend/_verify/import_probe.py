import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

t = time.perf_counter()
from app.main import app  # noqa: E402

print(f"IMPORT_OK in {time.perf_counter() - t:.1f}s")
