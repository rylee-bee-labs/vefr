"""The merge-base guard's own edges (review of vefr#538): a branch that
claims to be a refactor fails when its merge base cannot be measured, and
skips only when there is nothing to measure against."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weave_digest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_cache():
    weave_digest.merge_base_digests.cache_clear()
    yield
    weave_digest.merge_base_digests.cache_clear()


def test_an_unclaimed_branch_skips(monkeypatch):
    monkeypatch.delenv(weave_digest.REFACTOR_ENV, raising=False)
    with pytest.raises(weave_digest.NotMeasurable):
        weave_digest.assert_unchanged_from_merge_base("no_skin_weave", "0" * 64)


def test_a_claimed_branch_whose_base_will_not_weave_fails(monkeypatch, tmp_path):
    monkeypatch.setenv(weave_digest.REFACTOR_ENV, "1")
    broken = subprocess.CompletedProcess([], 1, stdout="", stderr="Traceback\nImportError: boom")
    monkeypatch.setattr(weave_digest.subprocess, "run", lambda *a, **k: broken)
    with pytest.raises(weave_digest.MeasurementFailed, match="could not be woven: ImportError: boom"):
        weave_digest._measure(tmp_path)


def test_a_measurement_failure_is_an_assertion_not_a_skip():
    assert issubclass(weave_digest.MeasurementFailed, AssertionError)
    assert not issubclass(weave_digest.MeasurementFailed, weave_digest.NotMeasurable)


def test_a_claimed_branch_missing_a_measured_key_fails(monkeypatch):
    monkeypatch.setenv(weave_digest.REFACTOR_ENV, "1")
    monkeypatch.setattr(weave_digest, "merge_base_digests", lambda: {"sample_data": "0" * 64})
    with pytest.raises(weave_digest.MeasurementFailed, match="did not measure 'no_skin_weave'"):
        weave_digest.assert_unchanged_from_merge_base("no_skin_weave", "0" * 64)
