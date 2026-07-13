#!/usr/bin/env python3
"""
ingest_codebase.py — language-agnostic codebase -> semantic-memory ingestion.

Walks any repository, extracts useful facts, and writes them to the
semantic-memory MCP store (facts + a dependency/structure graph), so Claude can
recall a project's shape, components, and dependencies on demand.

It is deterministic and language-agnostic:
  * Detects ecosystems by their manifest files and parses component name /
    description / version / dependencies for: Cargo (Rust), npm (JS/TS),
    Python (pyproject/setup.cfg), Go (go.mod), Maven (pom.xml), .NET (*.csproj),
    Composer (PHP), plus best-effort detection for Gradle, Ruby, Dart, Elixir.
  * Always captures: repo overview, language/extension stats, top-level layout,
    and README summary — even for codebases with no recognised manifest.
  * Builds graph edges: each component `belongs_to` the repo; internal
    `depends_on` edges link components whose dependency names resolve in-repo.

Writes go through the semantic-memory-mcp binary over stdio JSON-RPC (the same
mechanism the hooks use), so no extra services are required.

Usage:
  ingest_codebase.py --path /path/to/repo [--name NAME] [--namespace NS]
                     [--dry-run] [--no-graph] [--max-components N]
                     [--binary PATH] [--memory-dir DIR]

Exit status is 0 on success; partial failures are reported but non-fatal.
"""
import argparse, json, os, re, subprocess, sys, shutil
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except Exception:
    tomllib = None

IGNORE_DIRS = {".git", "node_modules", "target", "dist", "build", "out",
               ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
               "vendor", ".next", ".nuxt", ".gradle", "bin", "obj", ".idea",
               ".vscode", "coverage", ".cargo", ".tox", "Pods"}

LANG_BY_EXT = {
    ".rs": "Rust", ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".java": "Java",
    ".kt": "Kotlin", ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++",
    ".hpp": "C++", ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".dart": "Dart", ".ex": "Elixir", ".exs": "Elixir", ".scala": "Scala",
    ".sh": "Shell", ".lua": "Lua", ".r": "R", ".m": "Objective-C",
    ".sql": "SQL", ".vue": "Vue", ".svelte": "Svelte",
}


# ---------- binary / memory dir resolution ----------
def resolve_binary(explicit):
    if explicit:
        return explicit
    env = os.environ.get("SEMANTIC_MEMORY_MCP_BIN")
    if env and os.access(env, os.X_OK):
        return env
    which = shutil.which("semantic-memory-mcp")
    if which:
        return which
    for cand in (Path.home()/".cargo/bin/semantic-memory-mcp",
                 Path.home()/".local/bin/semantic-memory-mcp"):
        if cand.exists() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def resolve_dir(explicit):
    if explicit:
        return explicit
    return os.environ.get("SEMANTIC_MEMORY_DIR",
                          str(Path.home()/".hermes/semantic-memory.db"))


# ---------- repo walk ----------
def list_files(root):
    """Prefer git tracking; fall back to a filtered walk."""
    try:
        out = subprocess.run(["git", "-C", root, "ls-files"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return [os.path.join(root, p) for p in out.stdout.splitlines()]
    except Exception:
        pass
    files = []
    for dp, dirs, fns in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for fn in fns:
            files.append(os.path.join(dp, fn))
    return files


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "repo"


# ---------- manifest parsers -> component dicts ----------
# each component: {name, version, desc, deps:[names], kind, rel}
def parse_cargo(path, text):
    if not tomllib:
        return None
    try:
        d = tomllib.loads(text)
    except Exception:
        return None
    pkg = d.get("package")
    if not pkg:
        return None
    deps = list(d.get("dependencies", {}).keys())
    ver = pkg.get("version", "")
    if isinstance(ver, dict):
        ver = "(workspace)"
    return {"name": pkg.get("name", ""), "version": ver,
            "desc": (pkg.get("description") or "").strip(),
            "deps": deps, "kind": "Rust crate"}


def parse_npm(path, text):
    try:
        d = json.loads(text)
    except Exception:
        return None
    if not d.get("name"):
        return None
    deps = list(d.get("dependencies", {}).keys()) + list(d.get("devDependencies", {}).keys())
    return {"name": d.get("name", ""), "version": d.get("version", ""),
            "desc": (d.get("description") or "").strip(),
            "deps": deps, "kind": "npm package"}


def parse_pyproject(path, text):
    if not tomllib:
        return None
    try:
        d = tomllib.loads(text)
    except Exception:
        return None
    proj = d.get("project") or {}
    poetry = (d.get("tool") or {}).get("poetry") or {}
    name = proj.get("name") or poetry.get("name")
    if not name:
        return None
    desc = (proj.get("description") or poetry.get("description") or "").strip()
    ver = proj.get("version") or poetry.get("version") or ""
    deps = []
    for dep in proj.get("dependencies", []) or []:
        m = re.match(r"[A-Za-z0-9._-]+", str(dep))
        if m:
            deps.append(m.group(0))
    deps += list((poetry.get("dependencies") or {}).keys())
    return {"name": name, "version": ver, "desc": desc, "deps": deps,
            "kind": "Python package"}


def parse_gomod(path, text):
    m = re.search(r"^module\s+(\S+)", text, re.M)
    if not m:
        return None
    name = m.group(1)
    deps = re.findall(r"^\s+([^\s]+)\s+v[0-9]", text, re.M)
    return {"name": name, "version": "", "desc": "Go module",
            "deps": deps, "kind": "Go module"}


def parse_pom(path, text):
    try:
        import xml.etree.ElementTree as ET
        # strip namespace for simplicity
        clean = re.sub(r'xmlns(:\w+)?="[^"]+"', "", text, count=1)
        root = ET.fromstring(clean)
    except Exception:
        return None
    aid = root.findtext("artifactId")
    if not aid:
        return None
    desc = (root.findtext("description") or "").strip()
    ver = root.findtext("version") or ""
    deps = []
    for dep in root.findall(".//dependencies/dependency"):
        a = dep.findtext("artifactId")
        if a:
            deps.append(a)
    return {"name": aid, "version": ver, "desc": desc, "deps": deps,
            "kind": "Maven module"}


def parse_csproj(path, text):
    name = Path(path).stem
    deps = re.findall(r'<(?:PackageReference|ProjectReference)\s+Include="([^"]+)"', text)
    deps = [Path(d.replace("\\", "/")).stem for d in deps]
    return {"name": name, "version": "", "desc": ".NET project",
            "deps": deps, "kind": ".NET project"}


def parse_composer(path, text):
    try:
        d = json.loads(text)
    except Exception:
        return None
    if not d.get("name"):
        return None
    deps = list(d.get("require", {}).keys()) + list(d.get("require-dev", {}).keys())
    return {"name": d["name"], "version": d.get("version", ""),
            "desc": (d.get("description") or "").strip(),
            "deps": deps, "kind": "Composer package"}


MANIFESTS = [
    ("Cargo.toml", parse_cargo),
    ("package.json", parse_npm),
    ("pyproject.toml", parse_pyproject),
    ("go.mod", parse_gomod),
    ("pom.xml", parse_pom),
    ("composer.json", parse_composer),
]
# detect-only ecosystems (presence noted, no dep parse)
PRESENCE = {
    "build.gradle": "Gradle (JVM)", "build.gradle.kts": "Gradle (Kotlin DSL)",
    "Gemfile": "Ruby/Bundler", "pubspec.yaml": "Dart/Flutter",
    "mix.exs": "Elixir/Mix", "CMakeLists.txt": "CMake (C/C++)",
    "Package.swift": "Swift Package Manager", "setup.py": "Python (setup.py)",
    "requirements.txt": "Python (requirements)",
}


def first_readme_summary(root):
    for cand in ("README.md", "README.MD", "Readme.md", "README.rst", "README.txt"):
        p = os.path.join(root, cand)
        if os.path.isfile(p):
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            title = ""
            body = []
            for line in txt.splitlines():
                s = line.strip()
                if not title and s.startswith("#"):
                    title = s.lstrip("#").strip(); continue
                if title and s and not s.startswith(("#", "!", "[", "|", "```", "<")):
                    body.append(s)
                if len(" ".join(body)) > 400:
                    break
            summary = (title + " — " if title else "") + " ".join(body)
            return summary[:600].strip()
    return ""


# ---------- JSON-RPC to the binary ----------
def rpc(binary, memdir, calls, timeout=300):
    """calls: list of (rpc_id, tool_name, args_dict). Returns {rpc_id: result_obj}."""
    reqs = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                   "clientInfo": {"name": "ingest", "version": "1"}}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})]
    for rid, tool, args in calls:
        reqs.append(json.dumps({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                                "params": {"name": tool, "arguments": args}}))
    p = subprocess.run([binary, "--memory-dir", memdir],
                       input="\n".join(reqs) + "\n",
                       capture_output=True, text=True, timeout=timeout)
    res = {}
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if "result" in o and o.get("id"):
            try:
                res[o["id"]] = json.loads(o["result"]["content"][0]["text"])
            except Exception:
                res[o["id"]] = None
    return res


def add_facts(binary, memdir, facts, dry):
    """facts: list of (key, content, namespace, source). Returns {key: fact_id}."""
    ids = {}
    pending = list(facts)
    for attempt in range(4):
        pending = [f for f in pending if f[0] not in ids]
        if not pending:
            break
        calls = [(6000 + i, "sm_add_fact",
                  {"content": c, "namespace": ns, "source": src})
                 for i, (k, c, ns, src) in enumerate(pending)]
        if dry:
            for (k, c, ns, src) in pending:
                ids[k] = "dry:" + k
            break
        out = rpc(binary, memdir, calls)
        for i, (k, c, ns, src) in enumerate(pending):
            r = out.get(6000 + i)
            if r and r.get("ok"):
                ids[k] = r["fact_id"]
    return ids


def find_existing(binary, memdir, facts):
    """Return {key: fact_id} for facts whose identical content already exists in
    the same namespace (so re-ingest is idempotent and edges still resolve)."""
    def norm(s):
        return " ".join(str(s).split())
    calls = [(8000 + i, "sm_search",
              {"query": c[:200], "namespaces": [ns], "top_k": 1})
             for i, (k, c, ns, src) in enumerate(facts)]
    out = rpc(binary, memdir, calls)
    found = {}
    for i, (k, c, ns, src) in enumerate(facts):
        r = out.get(8000 + i)
        if not r or not r.get("ok"):
            continue
        res = r.get("results") or []
        if not res:
            continue
        top = res[0]
        same = norm(top.get("content", "")) == norm(c) or top.get("cosine_similarity", 0) >= 0.995
        if same:
            rid = top.get("result_id", "")
            found[k] = rid[len("fact:"):] if rid.startswith("fact:") else rid
    return found


def add_edges(binary, memdir, edges, dry):
    """edges: list of (src_id, tgt_id, relation, weight)."""
    if dry or not edges:
        return len(edges)
    done = 0
    todo = list(edges)
    for attempt in range(4):
        if not todo:
            break
        calls = [(7000 + i, "sm_add_graph_edge",
                  {"source": "fact:" + s, "target": "fact:" + t,
                   "edge_type": "Entity", "relation": rel, "weight": w})
                 for i, (s, t, rel, w) in enumerate(todo)]
        out = rpc(binary, memdir, calls)
        ok_idx = set()
        for i in range(len(todo)):
            r = out.get(7000 + i)
            if r and r.get("ok"):
                ok_idx.add(i)
        done += len(ok_idx)
        todo = [e for i, e in enumerate(todo) if i not in ok_idx]
    return done


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Ingest any codebase into semantic-memory.")
    ap.add_argument("--path", required=True, help="Path to the repository root")
    ap.add_argument("--name", help="Project name (default: directory basename)")
    ap.add_argument("--namespace", help="Memory namespace (default: code:<name-slug>)")
    ap.add_argument("--binary", help="Path to semantic-memory-mcp binary")
    ap.add_argument("--memory-dir", help="Memory store directory")
    ap.add_argument("--max-components", type=int, default=400)
    ap.add_argument("--no-graph", action="store_true", help="Skip graph edges")
    ap.add_argument("--dedupe", action="store_true",
                    help="Skip facts whose identical content already exists in the namespace "
                         "(idempotent re-ingest); reuses existing IDs so the graph still links up")
    ap.add_argument("--dry-run", action="store_true", help="Print plan, write nothing")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"error: {root} is not a directory", file=sys.stderr); sys.exit(2)
    name = args.name or os.path.basename(root.rstrip("/"))
    ns = args.namespace or ("code:" + slug(name))
    binary = resolve_binary(args.binary)
    memdir = resolve_dir(args.memory_dir)
    if not binary and not args.dry_run:
        print("error: semantic-memory-mcp binary not found (use --binary or cargo install)", file=sys.stderr)
        sys.exit(127)

    files = list_files(root)
    # language stats
    ext_counts = {}
    for f in files:
        e = os.path.splitext(f)[1].lower()
        lang = LANG_BY_EXT.get(e)
        if lang:
            ext_counts[lang] = ext_counts.get(lang, 0) + 1
    langs = sorted(ext_counts.items(), key=lambda x: -x[1])
    lang_str = ", ".join(f"{l} ({n})" for l, n in langs[:8]) or "no recognised source files"

    # components from manifests
    components = {}   # name -> comp dict (+ rel path)
    ecosystems = set()
    presence = set()
    for f in files:
        base = os.path.basename(f)
        rel = os.path.relpath(f, root)
        for mname, parser in MANIFESTS:
            if base == mname:
                try:
                    text = open(f, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                comp = parser(f, text)
                if comp and comp.get("name"):
                    comp["rel"] = rel
                    comp["manifest"] = mname
                    ecosystems.add(mname)
                    # keep first occurrence; dirs are unique enough
                    components.setdefault(comp["name"], comp)
        if base in PRESENCE:
            presence.add(PRESENCE[base])

    comp_names = set(components)
    # cap
    comp_list = list(components.values())[:args.max_components]
    truncated = len(components) - len(comp_list)

    readme = first_readme_summary(root)
    top_dirs = sorted([d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d))
                       and d not in IGNORE_DIRS and not d.startswith(".")])[:40]

    # ---- assemble facts ----
    eco_str = ", ".join(sorted(ecosystems)) or "none detected"
    pres_str = (", plus " + ", ".join(sorted(presence))) if presence else ""
    facts = []
    overview = (f"Codebase '{name}' (path: {root}). Languages: {lang_str}. "
                f"{len(files)} tracked files, {len(components)} components across manifests: {eco_str}{pres_str}. "
                f"Top-level dirs: {', '.join(top_dirs) or '(flat)'}. "
                + (f"README: {readme} " if readme else "")
                + f"(Ingested by ingest_codebase.py, Grade A from source.)")
    facts.append(("__repo__", overview[:1200], ns, f"{root} (codebase ingest)"))

    for c in comp_list:
        deps_internal = [d for d in c["deps"] if d in comp_names and d != c["name"]]
        ext_count = len(c["deps"]) - len(deps_internal)
        desc = c["desc"] or "(no description)"
        txt = (f"{c['name']}"
               + (f" v{c['version']}" if c["version"] else "")
               + f" [{name} / {c['kind']}] — {desc} "
               + f"Path: {c['rel']}. "
               + (f"Internal deps: {', '.join(deps_internal[:10])}. " if deps_internal else "Internal deps: none. ")
               + (f"({ext_count} external deps.) " if ext_count > 0 else "")
               + "(Grade A from manifest.)")
        facts.append((c["name"], txt[:800], ns, f"{root}/{c['rel']}"))

    # ---- dry run report ----
    if args.dry_run:
        print(f"# Ingestion plan for '{name}'  (namespace: {ns})")
        print(f"binary: {binary or '(not found — dry-run ok)'}   memory-dir: {memdir}")
        print(f"languages: {lang_str}")
        print(f"ecosystems: {eco_str}{pres_str}")
        print(f"components: {len(components)} (writing {len(comp_list)}"
              + (f", {truncated} truncated)" if truncated else ")"))
        print(f"facts to write: {len(facts)}")
        if not args.no_graph:
            n_belong = len(comp_list)
            n_dep = sum(1 for c in comp_list for d in c["deps"]
                        if d in comp_names and d != c["name"])
            print(f"graph edges: {n_belong} belongs_to + {n_dep} depends_on")
        print("\n-- repo fact --\n" + overview[:500])
        if comp_list:
            print("\n-- sample component fact --\n" + facts[1][1][:400])
        return

    # ---- write facts (with optional dedupe against existing namespace) ----
    existing = {}
    if args.dedupe:
        existing = find_existing(binary, memdir, facts)
        to_write = [f for f in facts if f[0] not in existing]
        print(f"dedupe: {len(existing)} already present (skipped), {len(to_write)} new to write")
    else:
        to_write = facts
    ids = dict(existing)
    ids.update(add_facts(binary, memdir, to_write, dry=False))
    repo_id = ids.get("__repo__")
    new_written = sum(1 for (k, *_ ) in to_write if k in ids and k != "__repo__")
    print(f"facts: {len(ids)}/{len(facts)} resolved "
          f"({new_written} newly written, {len(existing)} reused) -> namespace '{ns}'")

    # ---- write graph ----
    if not args.no_graph and repo_id:
        edges = []
        for c in comp_list:
            cid = ids.get(c["name"])
            if not cid:
                continue
            edges.append((cid, repo_id, "belongs_to", 1.0))
            for d in c["deps"]:
                if d in comp_names and d != c["name"] and ids.get(d):
                    # weight 3.0 if the dependency is a hub (many dependents)
                    edges.append((cid, ids[d], "depends_on", 1.0))
        done = add_edges(binary, memdir, edges, dry=False)
        print(f"graph edges created: {done}/{len(edges)}")

    print(f"done. Recall with: sm_search over namespace '{ns}'.")


if __name__ == "__main__":
    main()
