# OpenAR Knowledge Hub — Agent Z workbench

Lives only on the `todo` branch; never merged into `main`. Spec and receipts
live in the OpenRA repository (M-KHUB); this file tracks hub-side work only.

## Waiting on the user
- [ ] 「发布」: list the first Knowledge Package publicly — `agent-z/package-study@119b454` (+ docs `agent-z/package-docs@157493e`); contract `8d7c608` already on main (Review merged it as infrastructure, user to confirm)
- [x] USR-2: default branch is `main` (user, 2026-10-16)
- [x] #55: first record published — `main` 60ef198 (via the client's real publish path, run by Agent Z on the owner's delegation; scope review qualifies → fixed → endorses)

## Rules
- Push only `agent-z/<topic>` branches; `main` is the default branch and the
  only published state. Accepted branches are merged into `main`, then
  archived as `archive/agent-z/<topic>` tags and deleted.
- `main` carries records, schema, scripts and CI only: no TODO/receipts,
  internal paths, private links, credentials, host names or raw sessions.
- Keep it simple: stdlib-only scripts, small commits, one topic per branch.

## M1 — first real record end to end
- [x] skeleton: record contract, validator (+ append-only `--base`), index, CI — merged `a4d932e`
- [x] first real finding with hosted public evidence (`agent-z/first-finding@67287ce`; Review r2 content ACCEPT; rho wording + 100-200 title fixed) — public merge waits for the user (#55) and should go through the client's real publish path
  - 2026-10-15: branch now `b2fd089` (merged hub main for testItems/text-safety); record bytes unchanged — pinned sha256 `9e8dc0c8…` identical in the second-host re-run
- [x] validator text-safety + reserved namespaces — merged to main `32b95cc` (Review 10-14 16:00Z)
- [x] second clean host against public `main` 60ef198: catalog → subscribe (agent: saved) → human searchable → agent reads it framed → check 0 changed (OpenRA khub-next `docs/acceptance/knowledge/runs-20261016/40-khm1-main.txt`). Earlier: — agent legs PASS 2026-10-14 and re-run 2026-10-15 at `b2fd089` (OpenRA khub-next `docs/acceptance/khub/runs/e2e-second-host-*.txt`); human legs (adopt searchable, then agent query) = OpenRA #57

## M2 — community review and evolution
- [~] assessments on the first record: same-team content-review (endorses-in-scope) + the author's own rerun of one cell (new script/seed, 0.225 vs 0.203) — still **no independent assessment** (needs someone outside the author's team)
- [ ] independent assessment record on a real record (not by its author) — client: `review` (content-review, same-team for the author) / `contribute` (any check type, independence enforced)
- [ ] counter-evidence / scope correction from another host, history preserved
- [ ] retraction/supersession notice reaches subscribed hosts

## M3 — evidence-grounded paper review (consumer side, in OpenRA)
- [x] KR-01/02 claim-level review against subscribed records (OpenRA `ora knowledge review-paper` + Paper claim-review tab); stack accepted on main pending B co-sign (OpenRA `agent-z/khub-stack-main`, 2026-10-16)

## Knowledge Packages (2026-10-16/17)
- [x] package contract: `packages/<id>/package.json`, `package` locator, validator + index + tests — main `8d7c608`
- [ ] first package `huiel.paired-bootstrap-power-study` — `agent-z/package-study@119b454`; the client's `--rehearse` from public main reproduces its tree byte for byte (OpenRA `docs/acceptance/khub/package-e2e-20261016/63-package-rehearsal.txt`); waits for the user's 「发布」
- [ ] CONTRIBUTING: publishing a package; hosted scripts are read, never executed — `agent-z/package-docs@157493e` (with the package)
- [~] index facets per record (conditions, disclosures, checks) for Discover cards/filters — `agent-z/index-facets@700213a` (32/32); the client writes the same bytes; merging with OpenRA khub-next in train-1017c

## Contract additions
- [x] `testItems` evidence flag — merged to main `45cda4d` (25 unittest OK); client side in OpenRA khub-m1 `d2b6a66e`
- [ ] README describes `testItems` — `agent-z/readme-test-items@c497e12`
- [x] paths cannot carry `"` `<` `>` or backticks (merged 7646940) (quoted in reviewer frames and terminals) — `agent-z/path-chars@7646940` (26 unittest OK; registry validates); client side OpenRA khub-next `f2aae0b4`
