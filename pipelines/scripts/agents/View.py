"""The "smart" finance view from the command line (approver-additions plan §2d, owner C3; the module:
`pipelines/agents/views.py`) — until the web UI draws it (ADR-060), the same view the API returns.

Commands (from the project root):
    uv run python pipelines/scripts/agents/View.py --as 13 --ask "billed vs budget % by category for week 23, top 5"
        one structured model call (the `tools` role) picks the chart from the catalogue (it never sees data); a
        question without a week is asked back
    uv run python pipelines/scripts/agents/View.py --as 13 --choice '{"kind": "trend", "week": 30, "weeks": 26}'
        code only, no model call
    add  --pptx dev/_scratch/view.pptx  to draw it as one native-chart slide (read back: the file = the spec)

Reads:   PostgreSQL read-only through `finance_kpi` as the employee (RBAC, ADR-006); the `tools` role's models for
         --ask (ADR-045; llm.py cache and quota).
Writes:  only the --pptx file asked for.
Re-run:  safe.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pptx import Presentation  # noqa: E402

from pipelines.agents import monitoring, roles as roles_mod, views  # noqa: E402
from pipelines.agents.deck import readback, render  # noqa: E402
from pipelines.agents.deck import style as S  # noqa: E402
from pipelines.agents.graphs import models as m  # noqa: E402
from pipelines.agents.tools import context  # noqa: E402

FMT = {"SDR": S.AXIS_M, "%": S.AXIS_PCT, "days": S.AXIS_DAYS}


def slide(spec: m.ViewSpec) -> bytes:
    """One 16:9 slide: the caption and the view as a native chart (line for a trend, bars otherwise)."""
    import io
    prs = Presentation()
    prs.slide_width, prs.slide_height = S.WIDTH, S.HEIGHT
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    render._text(sl, render.El("tpl:caption", "text", render._in(0.6, 0.4, 12.1, 0.6), spec.caption,
                                {"size": S.BODY_PT, "bold": True, "color": S.NAVY}))
    kind = "line" if spec.choice.kind == "trend" else "bar" if spec.choice.kind == "category" else "column"
    render._chart(sl, render.El("chart:view", "chart", render._in(0.6, 1.2, 12.1, 5.6), chart={
        "type": kind, "categories": spec.categories, "fmt": FMT[spec.unit],
        "series": [(s.name, s.values) for s in spec.series]}))
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as", dest="employee", type=int, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ask", help="the question in words (≤ 300 characters)")
    g.add_argument("--choice", help="a ViewChoice as JSON (no model call)")
    ap.add_argument("--pptx", type=Path, help="also draw the view as a one-slide PPTX here")
    a = ap.parse_args()
    monitoring.init(entry="view", launched_by="cli")
    user = context.load_user(a.employee)
    if a.ask:
        choice, usage = views.choose(a.ask[:300], roles_mod.Roles())
        print(f"choice ({usage['calls']} model call(s), {usage['cached']} cached): "
              f"{json.dumps(choice.model_dump(exclude_none=True))}")
        if choice.week is None:
            print(views.ASK_WEEK)
            return
    else:
        choice = m.ViewChoice.model_validate_json(a.choice)
    try:
        spec = views.fetch(user, choice)
    except views.ViewUnavailable as exc:
        raise SystemExit(f"not shown: {exc}") from exc
    print(spec.caption)
    for i, c in enumerate(spec.categories):
        print(f"  {c:<45} " + "  ".join(f"{s.name}: {s.values[i]}" for s in spec.series))
    print("sources: " + "; ".join(f"{s['view']} [{s['filter']}]" for s in spec.sources))
    if a.pptx:
        data = slide(spec)
        got = next(it for sl in readback.read(data) for n, it in sl if n == "chart:view")
        same = got["categories"] == [str(c) for c in spec.categories] and all(
            [readback._num(v) for v in vals] == [readback._num(v) for v in s.values]
            for (_, vals), s in zip(got["series"], spec.series))
        if not same:
            raise SystemExit("the drawn chart differs from the view (read back)")
        a.pptx.parent.mkdir(parents=True, exist_ok=True)
        a.pptx.write_bytes(data)
        print(f"slide: {a.pptx} (read back: the file = the view)")


if __name__ == "__main__":
    main()
