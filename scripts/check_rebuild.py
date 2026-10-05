"""Compare generated numeric results tolerantly across BLAS implementations."""

import json
import math
import subprocess
from pathlib import Path


def compare(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            compare(a[k], b[k])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b, strict=True):
            compare(x, y)
    elif isinstance(a, (float, int)) and not isinstance(a, bool):
        assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6), (a, b)
    else:
        assert a == b, (a, b)


if __name__ == "__main__":
    for path in ("docs/report.json", "data/results.json"):
        original = json.loads(subprocess.check_output(["git", "show", f"HEAD:{path}"]))
        compare(original, json.loads(Path(path).read_text()))
    print("Rebuilt results match the committed experiment within numerical tolerance.")
