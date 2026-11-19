"""Path references check (Repository layout plan, ADR-072): every repository path written in a tracked text file
must exist, and no tracked text file may carry a local-tool name.

Run:     uv run python dev/tools/path_refs_check.py            (from the project root; CI step)
         uv run python dev/tools/path_refs_check.py --list     (print every dangling reference, the allow-list format)
Reads:   the text files of the working tree that git does not ignore (.gitignore files + .git/info/exclude), except
         Data/ (frozen artifacts); rules 1-2 also skip the records whose paths stay as written (dev/history/archive/,
         dev/db_audit/, db/migrations/ — an applied migration never changes, ADR-016).
Rules:   1. a token that starts with a top-level folder (`pipelines/…`, `dev/…`, `db/…`, `docs/…`, `ops/…`, `deploy/…`,
            `web/…`, `powerbi/…`, `Data/…`) names a file or folder that exists, or one git ignores (generated, local);
            a token followed by `<`, `{`, `*`, `[` or `$` is a template and is skipped;
         2. a relative Markdown link `](path)` resolves from its file's folder;
         3. none of the names in WORDS appears (case-insensitive), except on a line marked `refs-check: allow`
            (a library's own identifier).
         References that dangled before this check was written (deleted files named in a decision's history) are listed
         in dev/tools/path_refs_allow.txt (`<file>\t<reference>`); any other dangling reference fails.
Writes:  nothing. Re-run: safe. Exit 0 = clean, 1 = findings (printed).
"""
import base64
import re
import sys
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
ALLOW = ROOT / "dev" / "tools" / "path_refs_allow.txt"
TOPS = ("pipelines", "dev", "db", "docs", "ops", "deploy", "web", "powerbi", "Data", "tools", "Notebooks")
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}
SKIP_PREFIXES = ("Data/", "web/src/api/generated/")                     # neither rule: frozen or generated files
PATH_SKIP = ("dev/history/archive/", "dev/db_audit/", "db/migrations/",   # records: their paths stay as written
             "dev/tools/layout_map.json")
TEXT_EXT = {".py", ".md", ".yml", ".yaml", ".toml", ".json", ".ps1", ".sh", ".ts", ".tsx", ".mjs", ".js", ".sql",
            ".txt", ".cfg", ".ini", ".Dockerfile", ".dockerignore", ".gitignore", ".gitattributes", ".example"}
TEXT_NAMES = {"Dockerfile", "Caddyfile", ".gitignore", ".gitattributes", ".dockerignore"}
SKIP_FILES = {"uv.lock", "package-lock.json", "path_refs_allow.txt"}
# local-tool names that must not appear in a tracked file (base64, so this file does not carry them either)
WORDS = [base64.b64decode(w).decode() for w in (
    "Y2xhdWRl", "YW50aHJvcGlj", "Y29kZXg=", "Y28tYXV0aG9yZWQtYnk=", "Y29kaW5nIGFzc2lzdGFudA==", "Z3JhcGhpZnk=",
    "YWdlbnRzLm1k", "Lm1jcC5qc29u", "XGJtY3BcYg==", "Y29tcHV0ZXIgdXNl", "cHJldG9vbHVzZQ==", "cG9zdHRvb2x1c2U=",
    "b3B1c3BsYW4=")]
WORDS_RX = re.compile("|".join(w if w.startswith("\\b") else re.escape(w) for w in WORDS), re.I)
PATH_RX = re.compile(r"(?<![A-Za-z0-9_./\\@:-])((?:" + "|".join(TOPS) + r")/[A-Za-z0-9_./-]*[A-Za-z0-9_/])")
LINK_RX = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def _glob_rx(pat: str) -> str:
    out, i = "", 0
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out += "(?:.*/)?"; i += 3; continue
        if pat.startswith("**", i):
            out += ".*"; i += 2; continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        elif c == "[":
            j = pat.find("]", i)
            out += pat[i:j + 1] if j > i else re.escape(c)
            i = j if j > i else i
        else:
            out += re.escape(c)
        i += 1
    return out


def _load_rules():
    rules = []                                         # (base, regex, negated, dir_only, anchored)
    sources = [(ROOT / ".gitignore", ""), (ROOT / ".git" / "info" / "exclude", "")]
    sources += [(p, p.parent.relative_to(ROOT).as_posix() + "/") for p in ROOT.glob("*/.gitignore")]
    for path, base in sources:
        if not path.is_file():
            continue
        for ln in path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            neg = ln.startswith("!")
            ln = ln[1:] if neg else ln
            dir_only = ln.endswith("/")
            ln = ln.rstrip("/")
            anchored = "/" in ln
            rules.append((base, re.compile(_glob_rx(ln.lstrip("/")) + "$"), neg, dir_only, anchored))
    return rules


RULES = _load_rules()


def _match(rel: str, is_dir: bool) -> bool | None:
    hit = None
    for base, rx, neg, dir_only, anchored in RULES:
        if not rel.startswith(base) or (dir_only and not is_dir):
            continue
        sub = rel[len(base):]
        if rx.match(sub if anchored else sub.rsplit("/", 1)[-1]):
            hit = not neg
    return hit


def ignored(rel: str, is_dir: bool | None = None) -> bool:
    parts = rel.strip("/").split("/")
    for k in range(1, len(parts)):
        if _match("/".join(parts[:k]), True):
            return True
    if is_dir is None:
        is_dir = (ROOT / rel).is_dir() or rel.endswith("/")
    return bool(_match(rel.strip("/"), is_dir))


def text_files():
    stack = [ROOT]
    while stack:
        d = stack.pop()
        for p in sorted(d.iterdir()):
            rel = p.relative_to(ROOT).as_posix()
            if p.is_dir():
                if p.name in SKIP_DIRS or ignored(rel, True) or (rel + "/").startswith(SKIP_PREFIXES):
                    continue
                stack.append(p)
            elif not rel.startswith(SKIP_PREFIXES) and p.name not in SKIP_FILES and not ignored(rel, False) and (
                    p.suffix in TEXT_EXT or p.name in TEXT_NAMES):
                yield p, rel


def exists(ref: str) -> bool:
    ref = ref.rstrip(".")
    p = ROOT / ref
    return p.exists() or ignored(ref)


def main() -> int:
    allow = set()
    if ALLOW.is_file():
        allow = {ln for ln in ALLOW.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")}
    dangling, words, files = [], [], 0
    for p, rel in text_files():
        try:
            t = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files += 1
        seen = set()
        record = rel.startswith(PATH_SKIP)
        for m in ([] if record else PATH_RX.finditer(t)):
            ref, nxt = m.group(1), t[m.end():m.end() + 1]
            if nxt in "<{*[$" and nxt or "..." in ref or ref in seen:
                continue
            seen.add(ref)
            if not exists(ref):
                dangling.append(f"{rel}\t{ref}")
        if p.suffix == ".md" and not record:
            for m in LINK_RX.finditer(t):
                link = m.group(1)
                if re.match(r"^[a-z]+:", link) or link.startswith(("/", "<")) or link in seen:
                    continue
                seen.add(link)
                target = (p.parent / link).resolve()
                if not target.exists() and not ignored(target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else link):
                    dangling.append(f"{rel}\t{link}")
        for i, ln in enumerate(t.splitlines(), 1):
            if WORDS_RX.search(ln) and "refs-check: allow" not in ln:
                words.append(f"{rel}:{i}: {ln.strip()[:140]}")
    new = [d for d in dangling if d not in allow]
    if "--list" in sys.argv:
        print("\n".join(sorted(set(dangling))))
        return 0
    stale = sorted(allow - set(dangling))
    for d in new:
        print("dangling:", d.replace("\t", "  ->  "))
    for w in words:
        print("local-tool name:", w)
    if stale:
        print(f"note: {len(stale)} allow-list entries no longer dangle (remove them):", *stale[:5], sep="\n  ")
    if new or words:
        print(f"❌ {len(new)} dangling path reference(s), {len(words)} local-tool name(s) in {files} files")
        return 1
    print(f"✅ path references: {files} text files, every path resolves ({len(allow)} historical entries allowed); "
          "no local-tool name")
    return 0


if __name__ == "__main__":
    sys.exit(main())
