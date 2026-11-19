"""The API's OpenAPI schema as a committed file (FastAPI plan §9, API9 inventory): the frontend's typed client is
generated from it (ADR-060 (4)), and a change to any route, model or status shows as a diff in review.

    uv run python dev/tools/openapi_snapshot.py            write docs/api/openapi.json
    uv run python dev/tools/openapi_snapshot.py --check    exit 1 when the app's schema differs from the file (the CI)

Needs no database: the app is built, never served.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipelines.api import app as app_mod  # noqa: E402

FILE = ROOT / "docs" / "api" / "openapi.json"


def schema_text() -> str:
    spec = app_mod.create_app(access_log=None).openapi()
    return json.dumps(spec, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = schema_text()
    paths = len(json.loads(text)["paths"])
    if a.check:
        old = FILE.read_text(encoding="utf-8") if FILE.exists() else ""
        if old != text:
            print(f"✗ {FILE.relative_to(ROOT).as_posix()} differs from the app's schema: run "
                  "`uv run python dev/tools/openapi_snapshot.py` and commit the file")
            raise SystemExit(1)
        print(f"✅ OpenAPI snapshot: {paths} paths, the file = the app")
        return
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {FILE.relative_to(ROOT).as_posix()} ({paths} paths)")


if __name__ == "__main__":
    main()
