"""P7（P3 triage f008、P6 T7）：重播分批送出，每批各自受逾時限制；第二批起失敗即重啟 worker。"""

import pytest

from peditor.core import service as service_mod
from peditor.core.service import DocumentService, ServiceError


def test_replay_split_into_batches(monkeypatch):
    svc = DocumentService(command=["unused"])
    calls = []
    monkeypatch.setattr(
        svc, "_call", lambda op, **kw: calls.append((op, kw)) or {"new_revision": 7}
    )
    commands = [{"params": {}, "base_revision": 0}] * (2 * service_mod.REPLAY_BATCH + 3)
    assert svc._replay_batches("w", commands, 7, True, 3) == {"new_revision": 7}
    sizes = [len(kw["params"]["commands"]) for _, kw in calls]
    assert sizes == [service_mod.REPLAY_BATCH, service_mod.REPLAY_BATCH, 3]
    assert [kw["params"]["reset"] for _, kw in calls] == [True, False, False]
    assert [kw["expected_revision"] for _, kw in calls] == [3, None, None]


@pytest.mark.parametrize(("fail_at", "restarted"), [(0, False), (1, True)])
def test_replay_failure_restarts_after_first_batch(monkeypatch, fail_at, restarted):
    svc = DocumentService(command=["unused"])
    count = {"calls": 0, "restarts": 0}

    def call(op, **kw):
        count["calls"] += 1
        if count["calls"] - 1 == fail_at:
            raise ServiceError("VALIDATION_FAILED", "x")
        return {"new_revision": 1}

    monkeypatch.setattr(svc, "_call", call)
    monkeypatch.setattr(svc, "_restart", lambda: count.__setitem__("restarts", 1))
    commands = [{"params": {}, "base_revision": 0}] * (service_mod.REPLAY_BATCH + 1)
    with pytest.raises(ServiceError):
        svc._replay_batches("w", commands, 1, False)
    assert bool(count["restarts"]) is restarted
