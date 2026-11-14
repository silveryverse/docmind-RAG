"""Guards the dependency floors for packages with known CVEs.

The requirements file is the only place versions are pinned in this repo (no
lockfile), so the declared lower bounds must be at or above the fixed releases.
"""

import re
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"

# Minimum release that contains the fix for every advisory listed against the
# package. For python-multipart the listed advisories are fixed in 0.0.18
# (GHSA-59g5-xgcq-4qw3), 0.0.22 (GHSA-wp53-j4wj-2cfg), 0.0.27
# (GHSA-pp6c-gr5w-3c5g) and 0.0.30 (GHSA-5rvq-cxj2-64vf), so 0.0.30 is the
# floor that closes all of them.
FIXED_FLOORS = {
    "fastapi": "0.109.1",
    "httpx": "0.23.0",
    "python-multipart": "0.0.30",
    "uvicorn": "0.11.7",
}


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(p) for p in parts) or (0,)


def _declared_floors() -> dict[str, str]:
    floors: dict[str, str] = {}
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?\s*>=\s*([0-9][^,;\s]*)", line)
        if match:
            floors[match.group(1).lower()] = match.group(2)
    return floors


def test_cve_packages_are_pinned_at_or_above_fixed_versions():
    declared = _declared_floors()
    for package, fixed in FIXED_FLOORS.items():
        assert package in declared, f"{package} must stay a direct dependency"
        assert _version_tuple(declared[package]) >= _version_tuple(fixed), (
            f"{package}>={declared[package]} is below the fixed release {fixed}"
        )
