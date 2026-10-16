#!/usr/bin/env python3
"""Generate knowledge.json from entries/knowledge/*/record.json and
packages/*/package.json.

The index is a rebuildable projection of the records; it is never hand-edited.
Run with --check to verify the committed index is current without writing.

Row contract (shared with the other OpenAR hub indexes): id, name, summary,
delivery, version, revision, entryPath, entrySha256. `revision` is the git
object id of record.json (what `git hash-object record.json` prints), so a
reader can match the pinned bytes against any clone. Knowledge-only display
fields (kind, publicationStatus, evidenceCount) follow; the record itself is
the only authority.

Knowledge Packages are listed under a separate top-level `packages` key (the
shared `entries` row contract stays records only, so clients that predate
packages keep working): id, name, summary, version, revision, entryPath,
entrySha256, records (member `id@rN`).
"""

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "entries" / "knowledge"
PACKAGES = ROOT / "packages"


def git_blob_id(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def build() -> dict:
    rows = []
    if ENTRIES.is_dir():
        for record_path in sorted(ENTRIES.glob("*/record.json")):
            raw = record_path.read_bytes()
            record = json.loads(raw)
            rows.append(
                {
                    "id": record["id"],
                    "name": record["title"],
                    "summary": record["summary"],
                    "delivery": "record",
                    "version": f"r{record['revision']}",
                    "revision": git_blob_id(raw),
                    "entryPath": record_path.relative_to(ROOT).as_posix(),
                    "entrySha256": hashlib.sha256(raw).hexdigest(),
                    "kind": record["kind"],
                    "publicationStatus": record["publication"]["status"],
                    "evidenceCount": len(record["evidence"]),
                }
            )
    rows.sort(key=lambda row: row["id"])
    index = {"schemaVersion": 1, "entries": rows}
    packages = []
    if PACKAGES.is_dir():
        for manifest in sorted(PACKAGES.glob("*/package.json")):
            raw = manifest.read_bytes()
            package = json.loads(raw)
            packages.append(
                {
                    "id": package["id"],
                    "name": package["title"],
                    "summary": package["summary"],
                    "version": f"r{package['revision']}",
                    "revision": git_blob_id(raw),
                    "entryPath": manifest.relative_to(ROOT).as_posix(),
                    "entrySha256": hashlib.sha256(raw).hexdigest(),
                    "records": [f"{m['id']}@r{m['revision']}" for m in package["records"]],
                    "publicationStatus": package["publication"]["status"],
                }
            )
    if packages:
        index["packages"] = packages
    return index


def render(index: dict) -> str:
    return json.dumps(index, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    index = build()
    rendered = render(index)
    path = ROOT / "knowledge.json"
    if "--check" in sys.argv:
        current = path.read_text() if path.exists() else ""
        if current != rendered:
            sys.exit("knowledge.json is stale; run scripts/build-index.py and commit it")
        print(f"knowledge.json is current ({len(index['entries'])} records, {len(index.get('packages', []))} packages)")
        return
    path.write_text(rendered)
    print(f"wrote knowledge.json ({len(index['entries'])} records)")


if __name__ == "__main__":
    main()
