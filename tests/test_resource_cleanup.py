#
# test_resource_cleanup.py
#
# Offline tests that Catalog and ApiClient release their thread pools,
# connection pools and sessions.  No MAXARCAT_TOKEN required.
#

from unittest import mock

import pytest

import maxarcat_client
from maxarcat import Catalog


class TestApiClientClose:

    @staticmethod
    def test_close_shuts_down_pool_and_rest_client():
        client = maxarcat_client.ApiClient()
        pool = client.pool
        pool_manager = client.rest_client.pool_manager
        with mock.patch.object(pool_manager, 'clear', wraps=pool_manager.clear) as clear:
            client.close()
            clear.assert_called_once()
        assert client.pool is None
        assert client.rest_client.pool_manager is None
        with pytest.raises(ValueError):
            pool.apply_async(lambda: None)

    @staticmethod
    def test_close_is_idempotent():
        client = maxarcat_client.ApiClient()
        client.close()
        client.close()
        client.rest_client.close()

    @staticmethod
    def test_context_manager_closes():
        with maxarcat_client.ApiClient() as client:
            assert client.pool is not None
        assert client.pool is None

    @staticmethod
    def test_close_waits_for_outstanding_async_results():
        client = maxarcat_client.ApiClient()
        with mock.patch.object(client, '_ApiClient__call_api', return_value='ok'):
            result = client.call_api('/x', 'GET', async_req=True)
            assert client._async_results == [result]
            client.close()
        assert result.get(timeout=1) == 'ok'
        assert client._async_results == []
        assert client.last_response is None

    @staticmethod
    def test_async_results_pruned_when_ready():
        client = maxarcat_client.ApiClient()
        with mock.patch.object(client, '_ApiClient__call_api', return_value='ok'):
            first = client.call_api('/x', 'GET', async_req=True)
            first.wait(timeout=1)
            second = client.call_api('/x', 'GET', async_req=True)
            assert first not in client._async_results
            assert second in client._async_results
        client.close()

    @staticmethod
    def test_async_call_after_close_raises():
        client = maxarcat_client.ApiClient()
        client.close()
        with pytest.raises(ValueError):
            client.call_api('/x', 'GET', async_req=True)

    @staticmethod
    def test_remove_temp_files(tmp_path):
        client = maxarcat_client.ApiClient()
        path = tmp_path / 'download.bin'
        path.write_bytes(b'data')
        client.temp_files.append(str(path))
        client.temp_files.append(str(tmp_path / 'missing'))
        client.remove_temp_files()
        assert not path.exists()
        assert client.temp_files == []
        client.close()


class TestCatalogClose:

    @staticmethod
    def test_close_closes_api_clients_and_session():
        catalog = Catalog(token='fake-token')
        clients = [catalog._stac_api.api_client, catalog._coll_api.api_client, catalog._item_api.api_client]
        assert len({id(c) for c in clients}) == 3
        session = catalog._session
        catalog.last_response = object()
        with mock.patch.object(session, 'close', wraps=session.close) as session_close:
            catalog.close()
            session_close.assert_called_once()
        for client in clients:
            assert client.pool is None
            assert client.rest_client.pool_manager is None
        assert catalog.last_response is None
        catalog.close()  # idempotent

    @staticmethod
    def test_context_manager_closes():
        with Catalog(token='fake-token') as catalog:
            client = catalog._stac_api.api_client
            assert client.pool is not None
        assert client.pool is None

    @staticmethod
    def test_request_url_uses_session_and_closes_response():
        catalog = Catalog(token='fake-token')
        response = mock.MagicMock()
        response.status_code = 200
        response.headers = {}
        response.content = b'{"a": 1}'
        response.__enter__.return_value = response
        with mock.patch.object(catalog._session, 'get', return_value=response) as get:
            assert catalog.get_url_json('https://example.invalid/asset') == {'a': 1}
            get.assert_called_once_with('https://example.invalid/asset',
                                        headers={'Authorization': 'Bearer fake-token'})
        response.__exit__.assert_called_once()
        catalog.close()

    @staticmethod
    def test_call_api_clears_previous_response_first():
        catalog = Catalog(token='fake-token')
        catalog.last_response = 'stale'
        seen = []

        def function():
            seen.append(catalog.last_response)
            return 'body', 200, {}

        assert catalog._call_api(function) == 'body'
        assert seen == [None]
        assert catalog.last_response == 'body'
        catalog.close()
