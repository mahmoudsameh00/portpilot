"""PortPilot rebrand: old uploads stay valid; new names keep the same validation and RBAC.

Run: uv run python dev/tools/run.py dev/checks/retrieval/Brand_compatibility_check.py
Reads: the approved legacy DOCX example; Power BI source files. No databases or network.
Writes: nothing. Re-run: safe. Final Checkpoint: dev/checkpoints/retrieval/Brand_compatibility_check.md.
"""
# %% Setup
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
sys.path.insert(0, str(ROOT))
from pipelines.lib import uploads  # noqa: E402
from pipelines.lib.retrieval import User  # noqa: E402
from pipelines.agents.skill_loader import catalog  # noqa: E402


def changed_docx(data: bytes, replacements: dict[str, str]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as old, zipfile.ZipFile(out, "w") as new:
        for item in old.infolist():
            content = old.read(item)
            if item.filename.endswith(".xml"):
                text = content.decode("utf-8")
                for before, after in replacements.items():
                    text = text.replace(before, after)
                content = text.encode("utf-8")
            new.writestr(item, content)
    return out.getvalue()


# %% Phase 1 — Existing identity and both document brands
old = (ROOT / "docs/templates/NileGate_document_v1_example.docx").read_bytes()
user = User(employee_id=1, role="employee", ceiling=1, department="Operations")
legacy = uploads.validate_upload(old, "legacy.docx", user)
assert legacy.accepted, legacy.codes()
renamed = changed_docx(old, {"NILEGATE-DOC v1": "PORTPILOT-DOC v1", "NileGate": "PortPilot"})
retained = uploads.validate_upload(renamed, "renamed.docx", user)
assert retained.accepted, retained.codes()
assert [c["chunk_id"] for c in legacy.chunks] == [c["chunk_id"] for c in retained.chunks]
fresh = changed_docx(renamed, {"NG-OPS-PRC-0042": "PP-OPS-PRC-0042"})
current = uploads.validate_upload(fresh, "current.docx", user)
assert current.accepted, current.codes()
assert uploads.document_id("NG-OPS-PRC-0042") == "ng_ops_prc_0042"
assert uploads.document_id("PP-OPS-PRC-0042") == "pp_ops_prc_0042"
assert all(c["source"] == "PortPilot" for c in current.chunks)
assert len(current.chunks) == len(legacy.chunks) > 0
print("✅ Phase 1 validation passed. Old/new branding accepted; existing chunk IDs retained; new PP codes supported.")

# %% Phase 2 — Renaming does not relax the document contract
bad_dept = changed_docx(fresh, {"PP-OPS-PRC-0042": "PP-HR-PRC-0042"})
bad = uploads.validate_upload(bad_dept, "bad.docx", user)
assert not bad.accepted and "E_BAD_FIELD" in bad.codes()
foreign = changed_docx(fresh, {"PORTPILOT-DOC v1": "OTHER-DOC v1"})
assert "E_NO_METADATA_BLOCK" in uploads.validate_upload(foreign, "foreign.docx", user).codes()
assert current.document is not None
meta = {**current.document, "sensitivity_level": "3"}
assert any(r.code == "E_LEVEL_ABOVE_UPLOADER" for r in uploads.check_metadata(meta, user))
print("✅ Phase 2 validation passed. Department/code mismatch, unknown template and excess access still refused.")

# %% Phase 3 — Power BI paths resolve after the directory rename
project = ROOT / "powerbi/PortPilot_Finance.pbip"
pbip = json.loads(project.read_text(encoding="utf-8"))
report = project.parent / pbip["artifacts"][0]["report"]["path"]
definition = json.loads((report / "definition.pbir").read_text(encoding="utf-8"))
model = (report / definition["datasetReference"]["byPath"]["path"]).resolve()
assert model.is_relative_to(project.parent.resolve()) and (model / "definition.pbism").is_file()
count = 0
for directory in (report, model):
    for path in directory.rglob("*.json"):
        if ".pbi" not in path.parts:
            json.loads(path.read_text(encoding="utf-8"))
            count += 1
assert count >= 40
print(f"✅ Phase 3 validation passed. PBIP/report/model references resolve; {count} JSON files parse.")

# %% Phase 4 — The longer product name still fits prompt metadata and token limits
skills = catalog()
# every SKILL.md folder loads (was a fixed 10: the JIT plan's `arrival-advice` made it 11 and failed CI run #20)
on_disk = sorted(p.parent.name for p in (ROOT / "pipelines" / "agents" / "skills").glob("*/SKILL.md"))
assert len(skills) == len(on_disk) >= 11, (len(skills), on_disk)
print(f"✅ Phase 4 validation passed. {len(skills)} skills load within metadata/body limits.")

# %% Final Checkpoint
print("✅ Final Checkpoint: PortPilot compatibility checks passed; no database, network or artifact writes.")
