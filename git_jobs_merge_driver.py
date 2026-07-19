#!/usr/bin/env python3
"""Git merge driver for jobs.json, keyed by job "id".

jobs.json is scraper-owned and rewritten wholesale every ~12 min, so most
conflicts against it are trivial: one side (almost always "ours", a stray
tailoring-side edit) touches a handful of job entries while the other side
(the scraper) rewrites huge swaths of the file for unrelated reasons. Line-based
git merge sees that as a conflict even though the actual changes never overlap.
This driver resolves per-job, keyed by "id", instead of per-line:

  - job present on only one side (relative to base)      -> take that side
  - job unchanged on one side                             -> take the other side
  - job changed on both sides, touching different fields  -> union of fields
  - job changed on both sides, SAME field, different value -> real conflict,
    left unresolved (see below) rather than silently guessing

Registered via .gitattributes (`jobs.json merge=jobsjson`) + local git config
(see CLAUDE.md "Git sync" section for the one-time per-machine setup command).
This is a safety net, not the primary fix -- the primary fix is that no skill
should be writing tailoring metadata into jobs.json at all anymore (it goes to
Firestore via job_status_store.py instead), so this driver should rarely even
be invoked with real per-job changes on both sides.

Git calls this as: `git_jobs_merge_driver.py %O %A %B` where %O is the common
ancestor, %A is "ours" (also where the merged result must be written), %B is
"theirs". Exit 0 = resolved, wrote %A. Exit 1 = could not safely resolve;
%A is left untouched (so git marks the path as a normal merge conflict) and
the specific job id / field / two values in conflict are printed to stderr.
"""

import json
import sys


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_jobs(path, jobs):
    # Must match the scraper's own db_utils.save_jobs() formatting exactly
    # (ensure_ascii default True, indent=2, LF line endings) or every write
    # here reformats the entire ~9500-job file and reintroduces the same
    # full-file diff noise this driver exists to avoid.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(jobs, f, indent=2)


def index_by_id(jobs):
    return {j["id"]: j for j in jobs if isinstance(j, dict) and "id" in j}


def main():
    if len(sys.argv) != 4:
        print("usage: git_jobs_merge_driver.py <base> <ours> <theirs>", file=sys.stderr)
        return 1

    base_path, ours_path, theirs_path = sys.argv[1], sys.argv[2], sys.argv[3]

    try:
        base = load(base_path)
        ours = load(ours_path)
        theirs = load(theirs_path)
    except Exception as e:
        print(f"jobs.json merge driver: failed to parse JSON ({e}) -- leaving as a normal conflict", file=sys.stderr)
        return 1

    if not (isinstance(base, list) and isinstance(ours, list) and isinstance(theirs, list)):
        print("jobs.json merge driver: expected top-level JSON arrays -- leaving as a normal conflict", file=sys.stderr)
        return 1

    if ours == theirs:
        return 0  # already identical, nothing to do

    if ours == base:
        # Our side made no changes at all -- take theirs wholesale (the common case:
        # a tailoring-side session that never touched jobs.json in this window).
        dump_jobs(ours_path, theirs)
        print("jobs.json merge driver: ours unchanged from base -- took theirs entirely.", file=sys.stderr)
        return 0

    if theirs == base:
        # Scraper made no changes -- take ours wholesale.
        return 0

    base_idx = index_by_id(base)
    ours_idx = index_by_id(ours)
    theirs_idx = index_by_id(theirs)

    ordered_ids = []
    seen = set()
    for j in theirs:  # preserve the scraper's ordering as primary
        jid = j.get("id") if isinstance(j, dict) else None
        if jid is not None and jid not in seen:
            ordered_ids.append(jid)
            seen.add(jid)
    for j in ours:  # append anything only ours has, at the end
        jid = j.get("id") if isinstance(j, dict) else None
        if jid is not None and jid not in seen:
            ordered_ids.append(jid)
            seen.add(jid)

    merged = []
    notes = []
    hard_conflicts = []

    for jid in ordered_ids:
        b, o, t = base_idx.get(jid), ours_idx.get(jid), theirs_idx.get(jid)

        if o is None and t is not None:
            merged.append(t)
            continue
        if t is None and o is not None:
            # Missing on theirs (the scraper's side): if ours also didn't touch it,
            # honor the scraper's removal. Otherwise keep ours rather than silently
            # dropping a job the tailoring side actively has.
            if b is not None and b == o:
                notes.append(f"{jid}: removed upstream, kept removed")
            else:
                merged.append(o)
                notes.append(f"{jid}: missing upstream but changed locally -- kept ours")
            continue
        if o is None and t is None:
            continue
        if o == t:
            merged.append(t)
            continue
        if b is not None and o == b:
            merged.append(t)  # only theirs changed this job
            continue
        if b is not None and t == b:
            merged.append(o)  # only ours changed this job
            continue

        # Both sides changed this same job entry -- union the fields.
        merged_entry = dict(t)  # theirs (scraper) is the authoritative base for job data
        base_fields = b or {}
        for k, v in o.items():
            if k not in t:
                merged_entry[k] = v  # additive field only ours has -- keep it
            elif t.get(k) != v and base_fields.get(k) != v:
                hard_conflicts.append((jid, k, v, t.get(k)))
        merged.append(merged_entry)

    if hard_conflicts:
        print("jobs.json merge driver: could not auto-resolve -- true field-level conflicts:", file=sys.stderr)
        for jid, field, ours_val, theirs_val in hard_conflicts:
            print(f"  - job {jid!r}, field {field!r}: ours={ours_val!r}  theirs={theirs_val!r}", file=sys.stderr)
        print("Resolve manually (union both fields' intent, don't just pick one) and re-add.", file=sys.stderr)
        return 1

    dump_jobs(ours_path, merged)

    if notes:
        print("jobs.json merge driver: auto-resolved with notes:", file=sys.stderr)
        for note in notes[:50]:
            print(f"  - {note}", file=sys.stderr)
        if len(notes) > 50:
            print(f"  ... and {len(notes) - 50} more", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
