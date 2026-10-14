#!/usr/bin/env python3
"""Validate the registry: record.json contract, hosted evidence hashes,
disclosure/sensitive-content checks, and knowledge.json consistency.

Zero dependencies beyond the Python standard library. CI runs exactly this
script with no secrets and no install step; it never executes anything a
record carries. Passing it means the record is well-formed and its pinned
files match - it says nothing about whether the statement is true.

    python3 scripts/validate.py                 # validate the working tree
    python3 scripts/validate.py --base <ref>    # also enforce append-only history
"""

import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "entries" / "knowledge"
MAX_FILE_BYTES = 512 * 1024
MAX_ENTRY_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE = 32
HOSTED_SUFFIXES = {".csv", ".tsv", ".json", ".jsonl", ".md", ".txt", ".py", ".yaml", ".yml", ".log"}

KINDS = {"finding", "heuristic", "recipe"}
PUBLICATION_STATUSES = {"candidate", "accepted", "retracted", "superseded"}
RELATIONS = {"supports", "contradicts", "qualifies", "inconclusive"}
SOURCE_KINDS = {"run", "artifact", "paper", "code-test", "human-observation"}
DISCLOSURES = {"summary", "checkable-data", "reproducible-package"}
LOCATOR_TYPES = {"hosted", "git", "zenodo", "doi", "url"}
PINNED_LOCATORS = {"hosted", "git", "zenodo"}
LOCAL_STATES = {"candidate", "reviewed", "validated-in-scope", "contradicted", "deprecated"}
DECIDERS = {"user", "agent", "ai-assisted-local-audit", "none"}
CHECK_TYPES = {"static-package-check", "content-review", "analysis-recompute",
               "independent-rerun", "transfer-validation"}
RERUN_CHECKS = {"independent-rerun", "transfer-validation"}
ASSESSMENT_RESULTS = {"endorses-in-scope", "qualifies-scope", "disputes", "inconclusive"}
INDEPENDENCE = {"author", "same-team", "independent"}
RECORD_RELATIONS = {"supersedes", "qualifies", "contradicts", "related"}

RECORD_FIELDS = {
    "schemaVersion", "id", "kind", "revision", "title", "summary", "statement",
    "applicability", "testedScope", "evidence", "authorReport", "assessments",
    "reuseGuidance", "credit", "license", "publication", "disclosure", "files",
}
REQUIRED = RECORD_FIELDS - {"testedScope", "assessments", "reuseGuidance", "disclosure"}

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
# <namespace>.<slug>: the namespace is the submitting author's GitHub login.
RECORD_ID = re.compile(r"^[a-z0-9-]{1,39}\.[a-z0-9][a-z0-9-]{0,87}$")
EVIDENCE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
HANDLE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TARGET = re.compile(r"^[a-z0-9-]{1,39}\.[a-z0-9][a-z0-9-]{0,87}@r[1-9]\d*$")

# Content that must never reach a public record: local paths, local-only run
# identities, private network hosts, credentials and contact data. Pattern hits
# are reported by name only, never echoed.
SENSITIVE = [
    ("absolute home path", re.compile(r"(/home/|/Users/|/root/|[A-Za-z]:\\\\?Users)")),
    ("home-relative path", re.compile(r"(^|[\s\"'(])~/")),
    ("file URL", re.compile(r"file://", re.I)),
    ("local host", re.compile(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b", re.I)),
    ("private network address", re.compile(r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b")),
    ("internal host name", re.compile(r"\.(internal|local|lan)\b", re.I)),
    ("local run/session UUID", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    ("e-mail address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("API key", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential assignment", re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}")),
]

errors: list[str] = []


# Namespaces a record may not claim: they would read as a client's own voice.
RESERVED_NAMESPACES = {"openra", "openar", "ora", "system", "admin"}
# Readers frame each record in this tag when handing it to an agent; record
# text may not contain it, so no field can close the frame.
FRAME_TAG = "external-knowledge"


def forging_char(c: str) -> bool:
    """Characters that forge structure in a prompt or terminal: controls
    (ANSI escapes, newlines faking a context line), bidi overrides/isolates,
    zero-width and Unicode tag characters. Record strings are single-line."""
    o = ord(c)
    return (
        o < 0x20 or 0x7F <= o <= 0x9F
        or o == 0x061C or 0x200B <= o <= 0x200F or 0x202A <= o <= 0x202E
        or 0x2060 <= o <= 0x2064 or 0x2066 <= o <= 0x2069 or o == 0xFEFF
        or 0xE0000 <= o <= 0xE007F
    )


def unsafe_strings(value, path="") -> list:
    """Every string and object key anywhere in the record, checked."""
    found = []
    items = []
    if isinstance(value, str):
        if any(forging_char(c) for c in value):
            found.append(f"{path or '/'}: control, bidi, zero-width or tag characters")
        if FRAME_TAG in value.lower():
            found.append(f"{path or '/'}: contains the reader context frame tag")
    elif isinstance(value, dict):
        for key, child in value.items():
            found += unsafe_strings(key, f"{path}/{key!r}")
            items.append((f"{path}/{key}", child))
    elif isinstance(value, list):
        items = [(f"{path}/{i}", child) for i, child in enumerate(value)]
    for child_path, child in items:
        found += unsafe_strings(child, child_path)
    return found


def fail(where: str, message: str) -> None:
    errors.append(f"{where}: {message}")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_rel_path(raw) -> bool:
    if not isinstance(raw, str) or not raw or raw.startswith("/") or "\\" in raw:
        return False
    return all(part not in ("", ".", "..") for part in raw.split("/"))


def text(value, max_chars: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= max_chars


def text_list(value, max_items: int, max_chars: int) -> bool:
    return isinstance(value, list) and len(value) <= max_items and all(text(v, max_chars) for v in value)


def conditions(value) -> bool:
    """A flat map of condition facet -> short text (task, data, method, model,
    metric, budget, ...). Unknown facets are allowed; unknown values belong in
    `unknowns`, never guessed."""
    return (
        isinstance(value, dict)
        and len(value) <= 24
        and all(re.match(r"^[a-z][a-zA-Z0-9-]{0,31}$", k) and text(v, 500) for k, v in value.items())
    )


def scan_sensitive(where: str, body: str) -> None:
    for label, pattern in SENSITIVE:
        if pattern.search(body):
            fail(where, f"contains a {label}; remove it before publishing")


def check_credit(rid: str, credit) -> set:
    logins = set()
    if not isinstance(credit, dict) or set(credit) - {
        "authors", "evidenceContributors", "reviewers", "reproducers", "maintainers", "registrySubmitter",
    }:
        fail(rid, "credit has unknown fields")
        return logins
    authors = credit.get("authors")
    if not isinstance(authors, list) or not authors:
        fail(rid, "credit.authors must list who made the finding (the submitter is recorded separately)")
        authors = []
    for role in ("authors", "evidenceContributors", "reviewers", "reproducers", "maintainers"):
        people = credit.get(role, [])
        if not isinstance(people, list):
            fail(rid, f"credit.{role} must be a list")
            continue
        for person in people:
            if not isinstance(person, dict) or set(person) - {"name", "github", "contribution"} or not text(person.get("name"), 64):
                fail(rid, f"credit.{role} entries need a name (and at most github, contribution)")
                continue
            github = person.get("github")
            if github is not None:
                if not isinstance(github, str) or not HANDLE.match(github):
                    fail(rid, f"credit.{role} github must be a login without '@'")
                else:
                    logins.add(github.lower())
            if "contribution" in person and not text(person["contribution"], 300):
                fail(rid, f"credit.{role} contribution must be short text")
    submitter = credit.get("registrySubmitter")
    if not isinstance(submitter, str) or not HANDLE.match(submitter):
        fail(rid, "credit.registrySubmitter must be the GitHub login that filed the record")
    return logins


def check_locator(where: str, loc, hosted: dict) -> str:
    if not isinstance(loc, dict) or loc.get("type") not in LOCATOR_TYPES:
        fail(where, f"locator.type must be one of {sorted(LOCATOR_TYPES)}")
        return ""
    kind = loc["type"]
    allowed = {
        "hosted": {"type", "path", "anchor"},
        "git": {"type", "repo", "revision", "path", "sha256", "anchor"},
        "zenodo": {"type", "record", "file", "sha256", "anchor"},
        "doi": {"type", "doi", "anchor"},
        "url": {"type", "url", "retrieved", "anchor"},
    }[kind]
    if set(loc) - allowed:
        fail(where, f"{kind} locator has unknown fields {sorted(set(loc) - allowed)}")
    if "anchor" in loc and not text(loc["anchor"], 200):
        fail(where, "locator.anchor (rows, metric keys, page, table) must be short text")
    if kind == "hosted":
        if loc.get("path") not in hosted:
            fail(where, "hosted locator path must be listed in files")
    elif kind == "git":
        if not isinstance(loc.get("repo"), str) or not REPO.match(loc["repo"]):
            fail(where, "git locator repo must be owner/name on github.com")
        if not isinstance(loc.get("revision"), str) or not HEX40.match(loc["revision"]):
            fail(where, "git locator revision must be a 40-hex commit (no branches or tags)")
        if not safe_rel_path(loc.get("path")):
            fail(where, "git locator path must be a safe relative path")
        if "sha256" in loc and not (isinstance(loc["sha256"], str) and HEX64.match(loc["sha256"])):
            fail(where, "git locator sha256 must be 64-hex")
    elif kind == "zenodo":
        if not (isinstance(loc.get("record"), str) and loc["record"].isdigit()):
            fail(where, "zenodo locator record must be the numeric id of one version (not the concept record)")
        if not text(loc.get("file"), 200) or not (isinstance(loc.get("sha256"), str) and HEX64.match(loc["sha256"])):
            fail(where, "zenodo locator needs file and its sha256")
    elif kind == "doi":
        if not (isinstance(loc.get("doi"), str) and re.match(r"^10\.\d{4,9}/\S{1,200}$", loc["doi"])):
            fail(where, "doi locator needs a DOI like 10.1234/abc")
    elif kind == "url":
        if not (isinstance(loc.get("url"), str) and loc["url"].startswith("https://") and len(loc["url"]) <= 500):
            fail(where, "url locator must be https")
        if not (isinstance(loc.get("retrieved"), str) and DATE.match(loc["retrieved"])):
            fail(where, "url locator needs the retrieved date (YYYY-MM-DD)")
    return kind


def check_evidence(rid: str, evidence, hosted: dict) -> dict:
    by_id = {}
    if not isinstance(evidence, list) or not evidence or len(evidence) > MAX_EVIDENCE:
        fail(rid, f"evidence must list 1..{MAX_EVIDENCE} items; a record without readable evidence is a lead, not knowledge")
        return by_id
    for item in evidence:
        where = f"{rid} evidence {item.get('id') if isinstance(item, dict) else '?'}"
        if not isinstance(item, dict):
            fail(rid, "evidence items must be objects")
            continue
        extra = set(item) - {
            "id", "relation", "sourceKind", "disclosure", "title", "description", "locator",
            "comparison", "derivation", "originGroup", "limitations", "contributedBy",
        }
        if extra:
            fail(where, f"unknown fields {sorted(extra)}")
        eid = item.get("id")
        if not (isinstance(eid, str) and EVIDENCE_ID.match(eid)) or eid in by_id:
            fail(where, "evidence id must be a unique short slug")
            continue
        by_id[eid] = item
        if item.get("relation") not in RELATIONS:
            fail(where, f"relation must be one of {sorted(RELATIONS)}")
        if item.get("sourceKind") not in SOURCE_KINDS:
            fail(where, f"sourceKind must be one of {sorted(SOURCE_KINDS)}")
        if item.get("disclosure") not in DISCLOSURES:
            fail(where, f"disclosure must be one of {sorted(DISCLOSURES)}")
        if not text(item.get("title"), 120) or not text(item.get("description"), 2000):
            fail(where, "title and description are required")
        kind = check_locator(where, item.get("locator"), hosted)
        if item.get("disclosure") != "summary" and kind and kind not in PINNED_LOCATORS:
            fail(where, "checkable evidence needs a pinned locator (hosted, git@commit or zenodo version+hash); otherwise mark disclosure 'summary'")
        if not text(item.get("originGroup"), 64):
            fail(where, "originGroup (shared data/run/cohort lineage) is required so dependent evidence is counted once")
        if "comparison" in item and not conditions(item["comparison"]):
            fail(where, "comparison must be a flat map of short texts (arms, baseline, cohort, metric, scorer, ...)")
        if "derivation" in item and not text(item["derivation"], 1000):
            fail(where, "derivation must be short text")
        if not text_list(item.get("limitations", []), 16, 500):
            fail(where, "limitations must be a list of short texts")
        if "contributedBy" in item and not (isinstance(item["contributedBy"], str) and HANDLE.match(item["contributedBy"])):
            fail(where, "contributedBy must be a GitHub login")
    return by_id


def check_assessments(rid: str, assessments, evidence: dict, statement_hash: str, author_logins: set) -> None:
    if not isinstance(assessments, list):
        fail(rid, "assessments must be a list")
        return
    for n, a in enumerate(assessments):
        where = f"{rid} assessment #{n + 1}"
        allowed = {
            "assessor", "date", "statementSha256", "evidenceIds", "checkType", "result",
            "independence", "aiAssisted", "scope", "method", "limitations", "openObligations",
            "conflictsOfInterest", "resultEvidenceIds",
        }
        if not isinstance(a, dict) or set(a) - allowed:
            fail(where, "unknown fields")
            continue
        assessor = a.get("assessor")
        if not isinstance(assessor, dict) or not text(assessor.get("name"), 64) or set(assessor) - {"name", "github"}:
            fail(where, "assessor needs name (and optional github)")
            assessor = {}
        if not (isinstance(a.get("date"), str) and DATE.match(a["date"])):
            fail(where, "date must be YYYY-MM-DD")
        if a.get("statementSha256") != statement_hash:
            fail(where, "statementSha256 does not match the current statement; an assessment binds the exact text it reviewed (re-assess after a revision)")
        if not isinstance(a.get("evidenceIds"), list) or any(e not in evidence for e in a["evidenceIds"]):
            fail(where, "evidenceIds must reference this record's evidence")
        check = a.get("checkType")
        if check not in CHECK_TYPES:
            fail(where, f"checkType must be one of {sorted(CHECK_TYPES)}")
        if a.get("result") not in ASSESSMENT_RESULTS:
            fail(where, f"result must be one of {sorted(ASSESSMENT_RESULTS)}")
        independence = a.get("independence")
        if independence not in INDEPENDENCE:
            fail(where, f"independence must be one of {sorted(INDEPENDENCE)}")
        github = (assessor.get("github") or "").lower()
        if independence == "independent" and github and github in author_logins:
            fail(where, "an author cannot record an independent assessment of their own record")
        if not isinstance(a.get("aiAssisted"), bool):
            fail(where, "aiAssisted must be stated (true/false)")
        if not text(a.get("scope"), 1000) or not text(a.get("method"), 1000):
            fail(where, "scope (what exactly is endorsed) and method (what was actually checked) are required")
        if check in RERUN_CHECKS:
            produced = a.get("resultEvidenceIds")
            if not isinstance(produced, list) or not produced or any(e not in evidence for e in produced):
                fail(where, f"{check} must point at the evidence its own run produced (resultEvidenceIds); a model review without a new run is content-review")
        for field in ("limitations", "openObligations"):
            if not text_list(a.get(field, []), 16, 500):
                fail(where, f"{field} must be a list of short texts")
        if "conflictsOfInterest" in a and not text(a["conflictsOfInterest"], 500):
            fail(where, "conflictsOfInterest must be short text")


def check_record(record_dir: pathlib.Path) -> None:
    rid = record_dir.name
    record_path = record_dir / "record.json"
    if not record_path.is_file():
        fail(rid, "missing record.json")
        return
    raw = record_path.read_bytes()
    try:
        record = json.loads(raw)
    except ValueError as error:
        fail(rid, f"record.json is not JSON: {error}")
        return
    if not isinstance(record, dict):
        fail(rid, "record.json must be an object")
        return
    unknown = set(record) - RECORD_FIELDS
    if unknown:
        # Notably rejects a self-declared `validated`/`verified` flag: trust is
        # derived from assessments by each reader, never asserted by a record.
        fail(rid, f"unknown fields: {sorted(unknown)}")
    missing = REQUIRED - set(record)
    if missing:
        fail(rid, f"missing fields: {sorted(missing)}")
        return
    if record["schemaVersion"] != 1:
        fail(rid, "schemaVersion must be 1")
    if record["id"] != rid or not RECORD_ID.match(rid):
        fail(rid, "id must equal the directory name and be <github-login>.<slug> (lowercase)")
    elif rid.split(".", 1)[0] in RESERVED_NAMESPACES:
        fail(rid, f"namespace {rid.split('.', 1)[0]!r} is reserved")
    for problem in unsafe_strings(record):
        fail(rid, f"unsafe text at {problem}")
    if record["kind"] not in KINDS:
        fail(rid, f"kind must be one of {sorted(KINDS)} (observations travel as evidence, not records)")
    if not isinstance(record["revision"], int) or isinstance(record["revision"], bool) or record["revision"] < 1:
        fail(rid, "revision must be a positive integer")
    if not text(record["title"], 64) or not text(record["summary"], 1000):
        fail(rid, "title (<=64) and summary (<=1000) are required")

    statement = record["statement"]
    if not isinstance(statement, dict) or set(statement) - {"text", "qualifiers", "doesNotClaim"} or not text(statement.get("text"), 2000):
        fail(rid, "statement needs text (one atomic claim) and optional qualifiers/doesNotClaim")
        statement = {"text": ""}
    for field in ("qualifiers", "doesNotClaim"):
        if not text_list(statement.get(field, []), 16, 500):
            fail(rid, f"statement.{field} must be a list of short texts")
    statement_hash = sha256(statement["text"].encode("utf-8"))

    applicability = record["applicability"]
    if not isinstance(applicability, dict) or set(applicability) - {"conditions", "unknowns"} or not conditions(applicability.get("conditions")):
        fail(rid, "applicability.conditions must be a flat map of condition -> text")
    elif not text_list(applicability.get("unknowns", []), 16, 300):
        fail(rid, "applicability.unknowns must be a list of short texts")
    tested = record.get("testedScope")
    if tested is not None and (
        not isinstance(tested, dict) or set(tested) - {"conditions", "summary"}
        or not conditions(tested.get("conditions")) or not text(tested.get("summary"), 1000)
    ):
        fail(rid, "testedScope must have conditions and summary (or be null when nothing was tested)")

    files = record["files"]
    hosted = {}
    total = 0
    if not isinstance(files, list):
        fail(rid, "files must be a list (empty when nothing is hosted)")
        files = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
            fail(rid, "each file needs exactly path, sha256, bytes")
            continue
        path = item["path"]
        if not safe_rel_path(path) or not path.startswith("evidence/"):
            fail(rid, f"hosted file {path!r} must live under evidence/")
            continue
        if pathlib.PurePosixPath(path).suffix.lower() not in HOSTED_SUFFIXES:
            fail(rid, f"hosted file {path!r} has an unsupported type (data, text and small scripts only)")
        full = record_dir / path
        if full.is_symlink() or not full.is_file():
            fail(rid, f"hosted file {path!r} is missing or a symlink")
            continue
        body = full.read_bytes()
        if len(body) != item["bytes"] or sha256(body) != item["sha256"]:
            fail(rid, f"hosted file {path!r} does not match its manifest size/sha256")
        if len(body) > MAX_FILE_BYTES:
            fail(rid, f"hosted file {path!r} exceeds {MAX_FILE_BYTES} bytes; use a pinned git/zenodo locator")
        if full.stat().st_mode & 0o111:
            fail(rid, f"hosted file {path!r} must not be executable")
        try:
            scan_sensitive(f"{rid} {path}", body.decode("utf-8"))
        except UnicodeDecodeError:
            fail(rid, f"hosted file {path!r} must be UTF-8 text")
        hosted[path] = item
        total += len(body)
    if total > MAX_ENTRY_BYTES:
        fail(rid, f"hosted evidence exceeds {MAX_ENTRY_BYTES} bytes")
    for path in record_dir.rglob("*"):
        rel = path.relative_to(record_dir).as_posix()
        if path.is_symlink():
            fail(rid, f"symlink {rel!r} is not allowed")
        elif path.is_file() and rel != "record.json" and rel not in hosted:
            fail(rid, f"{rel!r} is not listed in files")

    evidence = check_evidence(rid, record["evidence"], hosted)
    if not any(e.get("disclosure") != "summary" for e in evidence.values()):
        # Allowed, but the record must not look independently checkable.
        if record["publication"].get("status") == "accepted" and not (record.get("disclosure") or {}).get("verifiabilityImpact"):
            fail(rid, "an accepted record with summary-only evidence must state disclosure.verifiabilityImpact")

    report = record["authorReport"]
    if not isinstance(report, dict) or set(report) - {"localState", "decidedBy", "note"} \
            or report.get("localState") not in LOCAL_STATES or report.get("decidedBy") not in DECIDERS:
        fail(rid, "authorReport needs localState and decidedBy: the author's own host state, displayed as a self-report only")
    elif "note" in report and not text(report["note"], 500):
        fail(rid, "authorReport.note must be short text")

    author_logins = check_credit(rid, record["credit"])
    check_assessments(rid, record.get("assessments", []), evidence, statement_hash, author_logins)

    guidance = record.get("reuseGuidance", {})
    if not isinstance(guidance, dict) or set(guidance) - {"reusable", "stillCheck", "sanityChecks"} \
            or any(not text_list(v, 16, 500) for v in guidance.values()):
        fail(rid, "reuseGuidance has reusable / stillCheck / sanityChecks lists")

    if not (isinstance(record["license"], str) and re.match(r"^[A-Za-z0-9.+-]{2,40}$", record["license"])):
        fail(rid, "license must be an SPDX id (CC-BY-4.0 recommended for records)")

    publication = record["publication"]
    if not isinstance(publication, dict) or set(publication) - {"status", "published", "relations", "notice"}:
        fail(rid, "publication has status, published, relations, notice")
    else:
        status = publication.get("status")
        if status not in PUBLICATION_STATUSES:
            fail(rid, f"publication.status must be one of {sorted(PUBLICATION_STATUSES)}")
        if not (isinstance(publication.get("published"), str) and DATE.match(publication["published"])):
            fail(rid, "publication.published must be YYYY-MM-DD")
        relations = publication.get("relations", [])
        if not isinstance(relations, list) or any(
            not isinstance(r, dict) or set(r) - {"type", "target", "note"}
            or r.get("type") not in RECORD_RELATIONS or not TARGET.match(str(r.get("target", "")))
            for r in relations
        ):
            fail(rid, "relations are {type, target: <id>@r<N>, note?}")
        if status in {"retracted", "superseded"} and not text(publication.get("notice"), 1000):
            fail(rid, f"a {status} record must keep a notice explaining why")

    disclosure = record.get("disclosure", {})
    if not isinstance(disclosure, dict) or set(disclosure) - {"omitted", "verifiabilityImpact"} \
            or not text_list(disclosure.get("omitted", []), 16, 300) \
            or ("verifiabilityImpact" in disclosure and not text(disclosure["verifiabilityImpact"], 1000)):
        fail(rid, "disclosure has omitted (what was withheld) and verifiabilityImpact")

    scan_sensitive(f"{rid} record.json", raw.decode("utf-8"))


def git_show(ref: str, path: str):
    result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    return json.loads(result.stdout) if result.returncode == 0 else None


def check_history(base: str) -> None:
    """Append-only rules against the base branch: a record can be revised,
    narrowed, contradicted or retracted, but published history cannot be
    silently rewritten."""
    for record_path in sorted(ENTRIES.glob("*/record.json")):
        rel = record_path.relative_to(ROOT).as_posix()
        old = git_show(base, rel)
        if old is None:
            continue
        new = json.loads(record_path.read_bytes())
        rid = new.get("id", rel)
        if old == new:
            continue
        if old["statement"] != new["statement"] or old["applicability"] != new["applicability"] \
                or old.get("testedScope") != new.get("testedScope"):
            if new["revision"] <= old["revision"]:
                fail(rid, "statement/applicability/testedScope changed without a new revision")
        elif new["revision"] < old["revision"]:
            fail(rid, "revision went backwards")
        new_evidence = {e["id"]: e for e in new["evidence"]}
        for item in old["evidence"]:
            if new_evidence.get(item["id"]) != item:
                fail(rid, f"published evidence {item['id']!r} was removed or edited; add new evidence instead")
        old_assessments = old.get("assessments", [])
        if new.get("assessments", [])[: len(old_assessments)] != old_assessments:
            fail(rid, "published assessments are append-only")
        for role in ("authors", "evidenceContributors", "reviewers", "reproducers"):
            if any(p not in new["credit"].get(role, []) for p in old["credit"].get(role, [])):
                fail(rid, f"credit.{role} entries cannot be removed")
        if old["publication"]["status"] in {"retracted", "superseded"} and new["publication"]["status"] != old["publication"]["status"]:
            fail(rid, "a retracted/superseded record cannot be silently reinstated; publish a new revision record")
    for old_path in subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", base, "entries/knowledge/"], cwd=ROOT, capture_output=True, text=True,
    ).stdout.split():
        if old_path.endswith("record.json") and not (ROOT / old_path).exists():
            fail(old_path, "published records cannot be deleted; retract them instead")


def main() -> None:
    if ENTRIES.is_dir():
        for record_dir in sorted(p for p in ENTRIES.iterdir()):
            if record_dir.is_symlink() or not record_dir.is_dir():
                fail(record_dir.name, "entries/knowledge may only contain record directories")
                continue
            check_record(record_dir)
    if "--base" in sys.argv:
        check_history(sys.argv[sys.argv.index("--base") + 1])
    for path in ROOT.rglob("*"):
        if path.is_symlink() and ".git" not in path.parts:
            fail(path.relative_to(ROOT).as_posix(), "symlinks are not allowed")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(f"{len(errors)} problem(s)")
    count = len(list(ENTRIES.glob("*/record.json"))) if ENTRIES.is_dir() else 0
    print(f"ok: {count} record(s) valid")


if __name__ == "__main__":
    main()
