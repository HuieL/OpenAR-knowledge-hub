# Contributing to the OpenAR Knowledge Hub

This repository is a static registry. There is no server, no account, and
nothing here is ever executed by CI or by a reader.

## Publishing a record

1. Choose **one atomic statement** — a finding (a checkable claim within a
   stated scope), a heuristic (a conditional rule of thumb) or a recipe (steps
   with preconditions, a check and a failure exit). Raw observations travel as
   evidence, not as records.
2. Create `entries/knowledge/<github-login>.<slug>/record.json` following
   `schemas/knowledge-record.schema.json`. In particular:
   - keep `applicability.conditions` (where you think it applies) separate
     from `testedScope` (what was actually tested); list unknown conditions in
     `applicability.unknowns` instead of guessing;
   - give every evidence item a `disclosure` level and a locator; anything
     other than `summary` needs a pinned locator — a hosted file with sha256,
     a `git` repo at a 40-hex commit, or one Zenodo **version** record with the
     file's sha256;
   - give every evidence item an `originGroup`: evidence derived from the same
     run, cohort or file shares a group and counts once;
   - put what you withheld in `disclosure.omitted` and say how that limits
     verification.
3. Run `python3 scripts/validate.py` and `python3 scripts/build-index.py`, and
   commit the regenerated `knowledge.json` with the record.
4. Open a PR. CI runs the validator (read-only, no secrets).

**CI passing means the record is well-formed and its hashes match. It is not a
scientific review.** New records enter as `publication.status: "candidate"`;
a maintainer sets `accepted` when the record is catalogued.

## What must never be published

Absolute or home-relative paths, local run/session ids, private hosts,
credentials or tokens, e-mail addresses, unpublished private code, raw agent
sessions, restricted data or sensitive samples. The validator rejects the
patterns it can recognise; you remain responsible for the rest. Deleting a
commit later does not remove copies others have cloned.

## Assessments, corrections and history

- Assessments are appended to `assessments[]`. Each one binds the exact
  statement text (`statementSha256`), names the evidence it looked at, the
  check actually performed, the result and the endorsed scope, whether it was
  AI-assisted, and its independence (`author` / `same-team` / `independent`).
- An `independent-rerun` or `transfer-validation` must point at the evidence
  its own run produced (`resultEvidenceIds`). A model reading the record again
  is a `content-review`, not a reproduction.
- An AI-assisted `content-review` (`aiAssisted: true`) checks that the
  statement, numbers and tested scope say no more than the record's own
  evidence shows. It runs nothing, consults nothing else, and does not make a
  record `accepted`. When the record's author or submitter delegated it, its
  independence is `same-team`; findings that narrow the wording belong in
  `limitations`, and the statement itself is revised only by a new revision.
- Published evidence and assessments are append-only (`validate.py --base
  origin/main` enforces this). Changing the statement, applicability or tested
  scope requires a new `revision`. Narrowing or contradicting someone else's
  record is done by adding evidence/assessments or a new record with a
  `qualifies` / `contradicts` relation — never by rewriting their conclusion.
- Records are retracted or superseded, never deleted; the notice stays.

## Credit

`credit` separates authors (who made the finding), evidence contributors,
reviewers, reproducers, maintainers and the registry submitter. Filing a record
does not make you its author. Negative results and scope corrections are
credited like any other contribution. Popularity and adoption counts never
change a record's scientific standing.
