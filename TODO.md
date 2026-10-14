# OpenAR Knowledge Hub — Agent Z workbench

Lives only on the `todo` branch; never merged into `main`. Spec and receipts
live in the OpenRA repository (M-KHUB); this file tracks hub-side work only.

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
- [ ] validator text-safety + reserved namespaces (`agent-z/text-safety@5eed6c3`, local only: no push access from the EC2 host)
- [ ] second clean host subscribes at a pinned commit and an agent reads it under matching conditions (client side ready; adoption to searchable is a human step)

## M2 — community review and evolution
- [ ] independent assessment record on a real record (not by its author) — client: `review` (content-review, same-team for the author) / `contribute` (any check type, independence enforced)
- [ ] counter-evidence / scope correction from another host, history preserved
- [ ] retraction/supersession notice reaches subscribed hosts

## M3 — evidence-grounded paper review (consumer side, in OpenRA)
