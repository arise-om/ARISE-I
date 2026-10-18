"""
tests/test_ai_layer.py
----------------------
Classifier, learning store and health monitor behaviour (v2.1 regressions).

These modules had no tests before v2.1.  Each test below pins a bug that
shipped in v2.0: Review-quarantined files were logged as a "__Review__"
training label, a retrained model was never picked up in-session, and the
health monitor re-ran the same retrain (and alert) every 60 seconds.
"""

import json
import logging
import os
import time
from pathlib import Path

import pytest

import classifier
import health_monitor
from file_organizer import DEFAULT_CATEGORIES, organize_folder
from learning_store import LearningStore

try:
    import sklearn  # noqa: F401
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@pytest.fixture(autouse=True)
def reset_logger():
    logger = logging.getLogger("arise_i")
    yield
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


@pytest.fixture
def store(tmp_path):
    return LearningStore(feedback_file=tmp_path / "feedback.jsonl",
                         model_file=tmp_path / "model.pkl",
                         retrain_threshold=10_000)


def _events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ── Learning store ──────────────────────────────────────────────────────────

class TestLearningLabels:

    def test_review_moves_are_not_training_labels(self, tmp_path, store):
        target = tmp_path / "dl"
        target.mkdir()
        (target / "mystery.xyz").write_text("x")   # unknown → __Review__
        (target / "paper.pdf").write_text("x")

        organize_folder(str(target), learning_store=store)

        labels = [e["confirmed"] for e in _events(tmp_path / "feedback.jsonl")]
        assert (target / "__Review__" / "mystery.xyz").exists()
        assert labels == ["PDFs"]

    def test_user_resolution_is_recorded_as_correction(self, tmp_path, store):
        store.record(Path("mystery.xyz"), predicted="__Review__", confirmed="Code",
                     confidence=0.1, layer="user_review")
        (event,) = _events(tmp_path / "feedback.jsonl")
        assert event["confirmed"] == "Code" and event["corrected"] is True

    @pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn not installed")
    def test_retrain_ignores_legacy_review_labels(self, tmp_path, store):
        rows = []
        for i in range(15):
            rows.append({"features": f"pdf pdf pdf paper{i}", "confirmed": "PDFs"})
            rows.append({"features": f"jpg jpg jpg photo{i}", "confirmed": "Images"})
            rows.append({"features": f"iso iso iso disk{i}", "confirmed": "__Review__"})
        (tmp_path / "feedback.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

        assert store.retrain()
        meta = json.loads((tmp_path / "model_meta.json").read_text())
        assert meta["labels"] == ["Images", "PDFs"]

    @pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn not installed")
    def test_single_class_is_not_trained(self, tmp_path, store):
        # A one-class Naive Bayes predicts that class at 100% for *every* file
        rows = [{"features": f"pdf pdf pdf p{i}", "confirmed": "PDFs"} for i in range(30)]
        (tmp_path / "feedback.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        assert store.retrain() is False


# ── Classifier ──────────────────────────────────────────────────────────────

class _FakePipeline:
    def __init__(self, proba):
        self._proba = proba

    def predict_proba(self, _texts):
        import numpy as np
        return np.array([self._proba])


class TestClassifier:

    def test_shared_classifier_reloads_retrained_model(self):
        clf = classifier.get_classifier(DEFAULT_CATEGORIES)
        model = Path.home() / ".arise-i" / "model.pkl"
        model.parent.mkdir(parents=True, exist_ok=True)
        model.write_bytes(b"not a real model")   # load fails gracefully
        future = time.time() + 5
        os.utime(model, (future, future))
        assert clf.model_is_stale()

        assert classifier.get_classifier(DEFAULT_CATEGORIES) is clf
        assert not clf.model_is_stale()
        model.unlink()

    def test_threshold_change_is_applied_to_shared_instance(self):
        clf = classifier.get_classifier(DEFAULT_CATEGORIES, confidence_threshold=0.75)
        classifier.get_classifier(DEFAULT_CATEGORIES, confidence_threshold=0.95)
        assert clf.confidence_threshold == 0.95
        classifier.get_classifier(DEFAULT_CATEGORIES, confidence_threshold=0.75)

    def test_model_never_predicts_review_folder(self, tmp_path, monkeypatch):
        pytest.importorskip("numpy")
        monkeypatch.setattr(classifier, "_SKLEARN_AVAILABLE", True)
        clf = classifier.SmartClassifier(DEFAULT_CATEGORIES, model_path=tmp_path / "none.pkl")
        clf._ml_pipeline = _FakePipeline([0.99, 0.01])
        clf._ml_labels = ["__Review__", "PDFs"]
        result = clf._by_model(Path("whatever.bin"))
        assert result.category == "Others" and result.confidence < 0.1

    def test_heuristic_falls_back_to_others_for_custom_categories(self):
        clf = classifier.SmartClassifier({"Work": [".pdf"]}, model_path=Path("missing.pkl"))
        assert clf._by_heuristics(Path("invoice_march.bin")).category == "Others"


# ── Health monitor ──────────────────────────────────────────────────────────

class _DriftingStore:
    def __init__(self):
        self.events = 40
        self.retrains = 0

    def correction_rate(self):
        return 0.5

    def total_events(self):
        return self.events

    def retrain(self):
        self.retrains += 1
        return True


class TestHealthMonitor:

    def test_drift_retrain_runs_once_until_new_feedback(self, monkeypatch):
        store = _DriftingStore()
        hm = health_monitor.HealthMonitor(learning_store=store)
        spawned = []
        monkeypatch.setattr(hm, "_do_retrain", lambda: None)
        monkeypatch.setattr(health_monitor.threading, "Thread",
                            lambda **kw: type("T", (), {"start": lambda s: spawned.append(1)})())

        for _ in range(3):
            hm._check_drift()
        assert len(spawned) == 1

        store.events += 5            # new feedback arrived
        hm._check_drift()
        assert len(spawned) == 2

    def test_orphan_reminder_is_emitted_once(self, tmp_path):
        review = tmp_path / "__Review__"
        review.mkdir()
        old = review / "stale.bin"
        old.write_text("x")
        week_ago = time.time() - 8 * 86400
        os.utime(old, (week_ago, week_ago))

        import queue
        q = queue.Queue()
        hm = health_monitor.HealthMonitor(target_dir=tmp_path, log_queue=q)
        hm._check_orphans()
        hm._check_orphans()
        messages = [q.get_nowait() for _ in range(q.qsize())]
        assert len(messages) == 1 and "stale.bin" in messages[0]

    def test_low_disk_warning_is_emitted_once(self, tmp_path, monkeypatch):
        import queue
        from collections import namedtuple
        usage = namedtuple("usage", "total used free")
        monkeypatch.setattr(health_monitor.shutil, "disk_usage",
                            lambda _p: usage(10**12, 10**12, 1024))
        q = queue.Queue()
        hm = health_monitor.HealthMonitor(target_dir=tmp_path, log_queue=q)
        hm._check_disk(tmp_path)
        hm._check_disk(tmp_path)
        assert q.qsize() == 1
