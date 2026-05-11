from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.routes import matching


class _FakeQuery:
    def __init__(self, model, data):
        self.model = model
        self.data = data
        self._job_offer_id = None

    def filter(self, *conditions):
        if self.model.__name__ in {"Match", "Candidate"}:
            for cond in conditions:
                right = getattr(cond, "right", None)
                if right is not None and hasattr(right, "value"):
                    self._job_offer_id = right.value
        return self

    def join(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        if self.model.__name__ == "JobOffer":
            return self.data["offer"]
        return None

    def all(self):
        if self.model.__name__ == "Match":
            return [m for m in self.data["matches"] if m.job_offer_id == self._job_offer_id]
        if self.model.__name__ == "Candidate":
            return [
                m.candidate
                for m in self.data["matches"]
                if m.job_offer_id == self._job_offer_id and m.candidate is not None
            ]
        return []


class _FakeDB:
    def __init__(self, offer, matches):
        self._data = {"offer": offer, "matches": matches}

    def query(self, model):
        return _FakeQuery(model, self._data)


class _Heuristic:
    def score(self, _offer, _candidate):
        return 0.5, {"source": "heuristic"}


class _Bert:
    ready = True
    load_error = None

    def score(self, _offer, _candidate):
        return 0.7, {"ready": True, "model": "mock", "inconsistencies": []}


def test_match_sandbox_filters_candidates_by_offer(monkeypatch):
    offer_id_a = uuid4()
    offer_id_b = uuid4()

    recruiter_id = uuid4()
    offer = SimpleNamespace(id=offer_id_a, recruiter_id=recruiter_id)

    candidate_a = SimpleNamespace(
        id=uuid4(),
        cv_id="cv-a",
        nom="Candidate A",
        email="a@test.local",
    )
    candidate_b = SimpleNamespace(
        id=uuid4(),
        cv_id="cv-b",
        nom="Candidate B",
        email="b@test.local",
    )

    match_a = SimpleNamespace(job_offer_id=offer_id_a, created_at=None, candidate=candidate_a)
    match_b = SimpleNamespace(job_offer_id=offer_id_b, created_at=None, candidate=candidate_b)

    db = _FakeDB(offer=offer, matches=[match_a, match_b])
    current_user = SimpleNamespace(role=SimpleNamespace(value="admin"), id=recruiter_id)

    monkeypatch.setattr(matching, "_get_heuristic_engine", lambda: _Heuristic())
    monkeypatch.setattr(matching, "_get_bert_scorer", lambda: _Bert())

    resp = matching.match_candidates_for_offer_sandbox(
        job_offer_id=offer_id_a,
        alpha=0.6,
        engine="compare_all",
        db=db,
        current_user=current_user,
    )

    assert resp["total"] == 1
    assert len(resp["results"]) == 1
    assert resp["results"][0]["cv_id"] == "cv-a"
