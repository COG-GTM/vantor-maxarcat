#
# test_issue_depot_memory.py
#
# Verifies the Issue Depot FastAPI service keeps its in-memory stores bounded
# under sustained bug-report traffic, evicting the oldest entries first.
#

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
ISSUE_DEPOT_MAIN = REPO_ROOT / 'src' / 'issue-depot' / 'app' / 'main.py'

MAX_SIZE = 50


@pytest.fixture()
def issue_depot():
    os.environ['ISSUE_DEPOT_MAX_DB_SIZE'] = str(MAX_SIZE)
    spec = importlib.util.spec_from_file_location('issue_depot_api_test', ISSUE_DEPOT_MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules['issue_depot_api_test'] = module
    spec.loader.exec_module(module)
    yield module
    del sys.modules['issue_depot_api_test']


@pytest.fixture()
def client(issue_depot):
    return TestClient(issue_depot.app)


def post_bug(client, i: int):
    response = client.post('/api/v1/bugs', json={
        'source': 'manual',
        'title': f'Bug number {i}',
        'description': f'Description for bug {i}',
        'raw_payload': {'index': i, 'blob': 'x' * 1000},
    })
    assert response.status_code == 200
    return response.json()['issue_id']


def test_dbs_remain_bounded_under_load(issue_depot, client):
    for i in range(MAX_SIZE * 3):
        post_bug(client, i)

    assert len(issue_depot.issues_db) <= MAX_SIZE
    assert len(issue_depot.assessments_db) <= MAX_SIZE


def test_oldest_entries_are_evicted(issue_depot, client):
    issue_ids = [post_bug(client, i) for i in range(MAX_SIZE + 20)]

    evicted = issue_ids[:20]
    retained = issue_ids[20:]

    for issue_id in evicted:
        assert issue_id not in issue_depot.issues_db
    for issue_id in retained:
        assert issue_id in issue_depot.issues_db


def test_evicted_bug_returns_404(issue_depot, client):
    issue_ids = [post_bug(client, i) for i in range(MAX_SIZE + 1)]

    response = client.get(f'/api/v1/bugs/{issue_ids[0]}')
    assert response.status_code == 404

    response = client.get(f'/api/v1/bugs/{issue_ids[-1]}')
    assert response.status_code == 200


def test_stored_bugs_have_no_raw_payload(issue_depot, client):
    for i in range(10):
        post_bug(client, i)

    for data in issue_depot.issues_db.values():
        assert 'raw_payload' not in data['bug']
