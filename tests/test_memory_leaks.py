#
# test_memory_leaks.py
#
# Tests verifying the memory-leak fixes in maxarcat and the Issue Depot service.
# All tests use mocks; no real API calls are made.
#

import gc
import importlib.util
import os
import sys
import tracemalloc
import weakref
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from maxarcat import Catalog

REPO_ROOT = Path(__file__).resolve().parent.parent
ISSUE_DEPOT_MAIN = REPO_ROOT / 'src' / 'issue-depot' / 'app' / 'main.py'


def load_issue_depot(module_name: str, max_size: str = None):
    """Load the issue-depot main module under a unique name (path contains a hyphen)."""
    if max_size is not None:
        os.environ['ISSUE_DEPOT_MAX_DB_SIZE'] = max_size
    spec = importlib.util.spec_from_file_location(module_name, ISSUE_DEPOT_MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def make_catalog() -> Catalog:
    return Catalog(token='fake-token')


class TestBoundedIssueDepotCache:
    """Test 1: Issue Depot in-memory stores are bounded LRU caches."""

    def test_eviction_keeps_cache_bounded(self):
        module = load_issue_depot('issue_depot_main_bounded', max_size='100')
        max_size = module.MAX_DB_SIZE
        assert max_size == 100

        for i in range(max_size + 100):
            module.issues_db[f'issue-{i}'] = {'bug': {'title': f'bug {i}'}}
            module.assessments_db[f'issue-{i}'] = {'severity': 'LOW'}

        assert len(module.issues_db) <= max_size
        assert len(module.assessments_db) <= max_size

    def test_oldest_entries_evicted_first(self):
        module = load_issue_depot('issue_depot_main_lru', max_size='100')
        max_size = module.MAX_DB_SIZE

        for i in range(max_size + 100):
            module.issues_db[f'issue-{i}'] = {'bug': {'title': f'bug {i}'}}

        for i in range(100):
            assert f'issue-{i}' not in module.issues_db
        for i in range(100, max_size + 100):
            assert f'issue-{i}' in module.issues_db

    def test_raw_payload_stripped_from_stored_issue(self):
        module = load_issue_depot('issue_depot_main_payload', max_size='100')
        from fastapi.testclient import TestClient

        client = TestClient(module.app)
        response = client.post('/api/v1/bugs', json={
            'source': 'manual',
            'title': 'Test bug',
            'description': 'A test bug',
            'raw_payload': {'huge': 'x' * 10000},
        })
        assert response.status_code == 200

        for data in module.issues_db.values():
            assert 'raw_payload' not in data['bug']


class TestSharedApiClient:
    """Test 2: all three API objects share a single ApiClient (one ThreadPool)."""

    def test_all_apis_share_one_api_client(self):
        catalog = make_catalog()
        try:
            assert catalog._stac_api.api_client is catalog._coll_api.api_client
            assert catalog._coll_api.api_client is catalog._item_api.api_client
            assert catalog._stac_api.api_client is catalog._api_client
        finally:
            catalog.close()

    def test_single_thread_pool(self):
        catalog = make_catalog()
        try:
            pools = {
                id(catalog._stac_api.api_client.pool),
                id(catalog._coll_api.api_client.pool),
                id(catalog._item_api.api_client.pool),
                id(catalog._api_client.pool),
            }
            assert len(pools) == 1
        finally:
            catalog.close()


class TestCatalogCleanup:
    """Test 3: close() and context manager shut down the thread pool deterministically."""

    def test_context_manager_closes_pool(self):
        with mock.patch('maxarcat_client.api_client.ThreadPool') as pool_cls:
            pool = pool_cls.return_value
            with make_catalog() as catalog:
                assert catalog._api_client is not None
            assert pool.close.called
            assert pool.join.called
            assert catalog._api_client is None

    def test_explicit_close(self):
        with mock.patch('maxarcat_client.api_client.ThreadPool') as pool_cls:
            pool = pool_cls.return_value
            catalog = make_catalog()
            catalog.close()
            assert pool.close.called
            assert pool.join.called
            assert catalog._api_client is None

    def test_close_is_idempotent(self):
        with mock.patch('maxarcat_client.api_client.ThreadPool'):
            catalog = make_catalog()
            catalog.close()
            catalog.close()
            assert catalog._api_client is None


class TestLastResponseWeakref:
    """Test 4: last_response does not prevent garbage collection of the response."""

    def test_last_response_is_weakref_and_allows_gc(self):
        catalog = make_catalog()
        try:
            class LargeResponse:
                payload = 'x' * 1000

            def fake_api_call():
                return (LargeResponse(), 200, {})

            body = catalog._call_api(fake_api_call)
            assert isinstance(catalog.last_response, weakref.ref)
            assert catalog.last_response() is body

            del body
            gc.collect()
            assert catalog.last_response() is None
        finally:
            catalog.close()

    def test_last_response_unweakrefable_falls_back_to_none(self):
        catalog = make_catalog()
        try:
            def fake_api_call():
                return ({'a': 1}, 200, {})  # dicts cannot be weak-referenced

            catalog._call_api(fake_api_call)
            assert catalog.last_response is None
        finally:
            catalog.close()


class TestQueryPagination:
    """Test 5: query() stops without issuing an extra empty request."""

    def test_query_stops_when_no_next_link(self):
        catalog = make_catalog()
        try:
            page1 = SimpleNamespace(
                features=[{'id': f'f{i}'} for i in range(10)],
                links=[{'rel': 'self'}, {'rel': 'next'}])
            page2 = SimpleNamespace(
                features=[{'id': f'g{i}'} for i in range(5)],
                links=[{'rel': 'self'}])

            with mock.patch.object(catalog, 'search', side_effect=[page1, page2]) as search:
                features = list(catalog.query(collections=['imagery']))

            assert len(features) == 15
            assert search.call_count == 2
        finally:
            catalog.close()

    def test_query_stops_on_empty_page(self):
        catalog = make_catalog()
        try:
            page1 = SimpleNamespace(features=[], links=None)
            with mock.patch.object(catalog, 'search', side_effect=[page1]) as search:
                features = list(catalog.query(collections=['imagery']))
            assert features == []
            assert search.call_count == 1
        finally:
            catalog.close()

    def test_query_handles_link_objects(self):
        catalog = make_catalog()
        try:
            page1 = SimpleNamespace(
                features=[{'id': 'f0'}],
                links=[SimpleNamespace(rel='next')])
            page2 = SimpleNamespace(features=[{'id': 'f1'}], links=[])
            with mock.patch.object(catalog, 'search', side_effect=[page1, page2]) as search:
                features = list(catalog.query(collections=['imagery']))
            assert len(features) == 2
            assert search.call_count == 2
        finally:
            catalog.close()


class TestMemoryGrowthStress:
    """Test 6: repeated search() calls do not accumulate memory."""

    def test_repeated_searches_do_not_accumulate_memory(self):
        catalog = make_catalog()
        try:
            class FeatureCollection:
                def __init__(self):
                    self.features = [{'id': f'feature-{i}', 'data': 'x' * 1000}
                                     for i in range(100)]
                    self.links = []

            def fake_api_call(*args, **kwargs):
                return (FeatureCollection(), 200, {})

            with mock.patch.object(
                    catalog._stac_api, 'post_search_stac_with_http_info',
                    side_effect=fake_api_call):
                gc.collect()
                tracemalloc.start()
                baseline, _ = tracemalloc.get_traced_memory()

                for _ in range(1000):
                    result = catalog.search(collections=['imagery'])
                    assert len(result.features) == 100
                    del result

                gc.collect()
                current, _ = tracemalloc.get_traced_memory()
                tracemalloc.stop()

            growth_mb = (current - baseline) / (1024 * 1024)
            assert growth_mb < 50, f'Memory grew by {growth_mb:.1f} MB'
        finally:
            catalog.close()
