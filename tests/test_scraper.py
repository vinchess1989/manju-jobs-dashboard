"""Unit tests for scraper.py logic.

Run with:  pytest tests/ -v
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# Allow importing scraper without triggering load_dotenv side-effects
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import scraper


# ---------------------------------------------------------------------------
# is_meaningful_reason
# ---------------------------------------------------------------------------

class TestIsMeaningfulReason:
    def test_rejects_single_word(self):
        assert scraper.is_meaningful_reason("test") is False

    def test_rejects_two_words(self):
        assert scraper.is_meaningful_reason("testing again") is False

    def test_rejects_test_prefix(self):
        assert scraper.is_meaningful_reason("testing the feature") is False

    def test_rejects_trying_prefix(self):
        assert scraper.is_meaningful_reason("trying something out") is False

    def test_accepts_substantive_reason(self):
        assert scraper.is_meaningful_reason("requires carpentry skills not relevant to candidate") is True

    def test_accepts_legal_reason(self):
        assert scraper.is_meaningful_reason("role is in Oulu and is entry level legal position") is True

    def test_rejects_empty(self):
        assert scraper.is_meaningful_reason("") is False

    def test_rejects_whitespace(self):
        assert scraper.is_meaningful_reason("   ") is False


# ---------------------------------------------------------------------------
# extract_json_from_text
# ---------------------------------------------------------------------------

class TestExtractJsonFromText:
    def test_plain_json(self):
        result = scraper.extract_json_from_text('{"match": "yes", "reason": "ok"}')
        assert result["match"] == "yes"

    def test_json_with_markdown_fence(self):
        text = '```json\n{"match": "no", "reason": "expired"}\n```'
        result = scraper.extract_json_from_text(text)
        assert result["match"] == "no"

    def test_json_embedded_in_prose(self):
        text = 'Here is the result: {"match": "maybe", "reason": "border case"} — done.'
        result = scraper.extract_json_from_text(text)
        assert result["match"] == "maybe"

    def test_raises_on_invalid(self):
        with pytest.raises(Exception):
            scraper.extract_json_from_text("no json here at all")


# ---------------------------------------------------------------------------
# classify_requirements_change
# ---------------------------------------------------------------------------

class TestClassifyRequirementsChange:
    OLD = "## Hard Rejections\n* Senior roles.\n"
    NEW_STRICTER = "## Hard Rejections\n* Senior roles.\n* Carpentry jobs.\n"
    NEW_LOOSER = "# No hard rejections anymore.\n"

    def _mock_post(self, json_body):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(json_body)}}]
        }
        return mock_resp

    @patch.dict(os.environ, {"LOCAL_LLM_ENDPOINT": "http://localhost:11434/v1/chat/completions", "LOCAL_LLM_MODEL": "llama3"})
    @patch("scraper.requests.post")
    def test_returns_true_when_llm_says_only_adds(self, mock_post):
        mock_post.return_value = self._mock_post({"only_adds_constraints": True})
        assert scraper.classify_requirements_change(self.OLD, self.NEW_STRICTER) is True

    @patch.dict(os.environ, {"LOCAL_LLM_ENDPOINT": "http://localhost:11434/v1/chat/completions", "LOCAL_LLM_MODEL": "llama3"})
    @patch("scraper.requests.post")
    def test_returns_false_when_llm_says_loosened(self, mock_post):
        mock_post.return_value = self._mock_post({"only_adds_constraints": False})
        assert scraper.classify_requirements_change(self.OLD, self.NEW_LOOSER) is False

    def test_returns_false_when_no_llm_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            assert scraper.classify_requirements_change(self.OLD, self.NEW_STRICTER) is False

    @patch.dict(os.environ, {"LOCAL_LLM_ENDPOINT": "http://localhost:11434/v1/chat/completions", "LOCAL_LLM_MODEL": "llama3"})
    @patch("scraper.requests.post", side_effect=Exception("timeout"))
    def test_falls_back_to_false_on_network_error(self, mock_post):
        assert scraper.classify_requirements_change(self.OLD, self.NEW_STRICTER) is False


# ---------------------------------------------------------------------------
# check_requirements_update — selective flagging
# ---------------------------------------------------------------------------

class TestCheckRequirementsUpdate:
    def _write_checkpoint(self, tmp_path, req_content, req_hash):
        cp = {"requirements_hash": req_hash, "requirements_content": req_content}
        (tmp_path / "checkpoint.json").write_text(json.dumps(cp), encoding="utf-8")

    def test_only_yes_maybe_flagged_when_constraints_only(self, jobs_file, req_file, tmp_path):
        old_hash = "oldhash000"
        old_content = "## Hard Rejections\n* Senior roles.\n"
        self._write_checkpoint(tmp_path, old_content, old_hash)

        with patch.object(scraper, "JOBS_FILE", jobs_file), \
             patch.object(scraper, "REQ_FILE", req_file), \
             patch.object(scraper, "CHECKPOINT_FILE", str(tmp_path / "checkpoint.json")), \
             patch("scraper.classify_requirements_change", return_value=True):
            scraper.check_requirements_update()

        with open(jobs_file) as f:
            jobs = json.load(f)

        yes_job   = next(j for j in jobs if j["matches_requirements"] == "yes")
        no_job    = next(j for j in jobs if j["matches_requirements"] == "no")
        done_job  = next(j for j in jobs if j["user_review"] == "done")

        assert yes_job.get("needs_re_review") is True
        assert no_job.get("needs_re_review") is None   # "no" jobs skipped
        assert done_job.get("needs_re_review") is None  # done jobs never touched

    def test_all_non_done_flagged_when_constraints_loosened(self, jobs_file, req_file, tmp_path):
        old_hash = "oldhash000"
        old_content = "## Hard Rejections\n* Senior roles.\n* Carpentry jobs.\n"
        self._write_checkpoint(tmp_path, old_content, old_hash)

        with patch.object(scraper, "JOBS_FILE", jobs_file), \
             patch.object(scraper, "REQ_FILE", req_file), \
             patch.object(scraper, "CHECKPOINT_FILE", str(tmp_path / "checkpoint.json")), \
             patch("scraper.classify_requirements_change", return_value=False):
            scraper.check_requirements_update()

        with open(jobs_file) as f:
            jobs = json.load(f)

        done_job = next(j for j in jobs if j["user_review"] == "done")
        non_done = [j for j in jobs if j["user_review"] != "done"]

        assert done_job.get("needs_re_review") is None
        assert all(j.get("needs_re_review") is True for j in non_done)


# ---------------------------------------------------------------------------
# poll_firebase_feedback — user_reason cleared on blank override
# ---------------------------------------------------------------------------

class TestPollFirebaseFeedback:
    JOB_URL = "https://example.com/job/1"

    def _make_firestore_response(self, reason):
        """Build a minimal Firestore REST response for one feedback doc."""
        return {
            "documents": [{
                "name": "projects/p/databases/(default)/documents/user_feedback/doc1",
                "fields": {
                    "status":   {"stringValue": "unread"},
                    "type":     {"stringValue": "negative"},
                    "url":      {"stringValue": self.JOB_URL},
                    "reason":   {"stringValue": reason},
                }
            }]
        }

    @patch("scraper.requests.patch")
    @patch("scraper.requests.get")
    def test_blank_reason_clears_user_reason_in_jobs(self, mock_get, mock_patch, jobs_file):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: self._make_firestore_response(""))
        mock_patch.return_value = MagicMock(status_code=200)

        with patch.object(scraper, "JOBS_FILE", jobs_file), \
             patch.object(scraper, "REQ_FILE", "nonexistent_req.md"):
            scraper.poll_firebase_feedback()

        with open(jobs_file) as f:
            jobs = json.load(f)
        job = next(j for j in jobs if j["url"] == self.JOB_URL)
        assert job["matches_requirements"] == "no"
        assert job["user_reason"] == ""          # stale "testing reason" must be cleared

    @patch("scraper.requests.patch")
    @patch("scraper.requests.get")
    def test_low_quality_reason_not_written_to_req_file(self, mock_get, mock_patch, jobs_file, req_file):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: self._make_firestore_response("testing again"))
        mock_patch.return_value = MagicMock(status_code=200)

        with patch.object(scraper, "JOBS_FILE", jobs_file), \
             patch.object(scraper, "REQ_FILE", req_file):
            scraper.poll_firebase_feedback()

        content = open(req_file).read()
        assert "testing again" not in content

    @patch("scraper.requests.patch")
    @patch("scraper.requests.get")
    def test_meaningful_reason_written_to_req_file(self, mock_get, mock_patch, jobs_file, req_file):
        reason = "job requires carpentry skills not relevant to law candidate"
        mock_get.return_value = MagicMock(status_code=200, json=lambda: self._make_firestore_response(reason))
        mock_patch.return_value = MagicMock(status_code=200)

        with patch.object(scraper, "JOBS_FILE", jobs_file), \
             patch.object(scraper, "REQ_FILE", req_file):
            scraper.poll_firebase_feedback()

        content = open(req_file).read()
        assert reason in content
