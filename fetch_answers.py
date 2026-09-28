"""Print the saved application answers for one job as plain JSON.

Usage:  venv\\Scripts\\python.exe fetch_answers.py <job_id>

Used by the apply-job skill. application_answers is readable only by the allow-listed
dashboard accounts or this project's service account (Firestore rules tightened 2026-09-28),
so the skill can no longer fetch the document anonymously - it runs this script instead,
which authenticates through firestore_auth.
"""
import json
import sys

import firestore_auth

DOC_URL = (f"https://firestore.googleapis.com/v1/projects/{firestore_auth.PROJECT_ID}"
           "/databases/(default)/documents/application_answers/{job_id}")


def _unwrap(value):
    """Firestore typed JSON ({"stringValue": ...}, {"mapValue": ...}, ...) -> plain Python."""
    if "mapValue" in value:
        return {k: _unwrap(v) for k, v in value["mapValue"].get("fields", {}).items()}
    if "arrayValue" in value:
        return [_unwrap(v) for v in value["arrayValue"].get("values", [])]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "nullValue" in value:
        return None
    return next(iter(value.values()), None)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: fetch_answers.py <job_id>")
    job_id = sys.argv[1].strip()
    resp = firestore_auth.session().get(DOC_URL.format(job_id=job_id), timeout=30)
    if resp.status_code == 404:
        sys.exit(f"No saved answers for job {job_id}.")
    resp.raise_for_status()
    fields = resp.json().get("fields", {})
    print(json.dumps({k: _unwrap(v) for k, v in fields.items()}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
