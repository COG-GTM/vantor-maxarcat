import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import BoundedStore


def test_bounded_store_evicts_oldest():
    store = BoundedStore(maxsize=3)
    for i in range(5):
        store[f'k{i}'] = i
    assert list(store) == ['k2', 'k3', 'k4']
    assert len(store) == 3


def test_bounded_store_update_does_not_evict():
    store = BoundedStore(maxsize=2)
    store['a'] = 1
    store['b'] = 2
    store['a'] = 3
    assert dict(store) == {'a': 3, 'b': 2}


def test_bounded_store_rejects_zero_capacity():
    with pytest.raises(ValueError):
        BoundedStore(maxsize=0)


def test_default_capacity_from_env():
    assert main.issues_db.maxsize == main.ISSUE_DEPOT_MAX_ISSUES
    assert main.assessments_db.maxsize == main.ISSUE_DEPOT_MAX_ISSUES


def test_receive_bug_report_evicts_beyond_capacity(monkeypatch):
    monkeypatch.setattr(main, 'issues_db', BoundedStore(maxsize=2))
    monkeypatch.setattr(main, 'assessments_db', BoundedStore(maxsize=2))
    client = TestClient(main.app)

    ids = []
    for i in range(3):
        resp = client.post('/api/v1/bugs', json={
            'source': 'manual',
            'title': f'Bug {i}',
            'description': 'x' * 10,
            'raw_payload': {'blob': 'y' * 1000},
        })
        assert resp.status_code == 200, resp.text
        ids.append(resp.json()['issue_id'])

    assert len(main.issues_db) == 2
    assert len(main.assessments_db) == 2
    assert ids[0] not in main.issues_db
    assert ids[1] in main.issues_db and ids[2] in main.issues_db

    assert client.get(f'/api/v1/bugs/{ids[0]}').status_code == 404
    assert client.get(f'/api/v1/bugs/{ids[2]}').status_code == 200
    assert client.get('/api/v1/stats').json()['total_bugs'] == 2
    assert client.get('/api/v1/bugs').json()['total'] == 2
