#
# conftest.py
#
# Pytest fixtures.
#


import os
from unittest.mock import MagicMock, patch

import pytest

from maxarcat import Catalog
from maxarcat_client.models.item_collection import ItemCollection


@pytest.fixture(scope='session')
def maxarcat_token() -> str:
    try:
        return os.environ['MAXARCAT_TOKEN']
    except Exception:
        pytest.exit('Must set environment variable MAXARCAT_TOKEN to run tests', returncode=1)


@pytest.fixture(scope='session')
def maxar_catalog_url() -> str:
    return os.environ.get('MAXAR_CATALOG_URL', 'https://api.content.maxar.com/catalog')


@pytest.fixture(scope='session')
def catalog(maxarcat_token, maxar_catalog_url) -> Catalog:
    return Catalog(token=maxarcat_token, url=maxar_catalog_url)


@pytest.fixture
def mock_catalog():
    """
    Catalog with mocked API calls for unit testing.
    Returns a tuple of (catalog, mock_call_api) so tests can configure mock responses.
    """
    with patch.object(Catalog, '__init__', lambda self, token, url=None: None):
        cat = Catalog.__new__(Catalog)
        cat._token = 'mock_token'
        cat.url = 'https://mock.api.com/catalog'
        cat.last_response = None
        cat._stac_api = MagicMock()
        cat._coll_api = MagicMock()
        cat._item_api = MagicMock()
    return cat


@pytest.fixture
def request_counter():
    """
    Fixture that counts HTTP requests made during pagination.
    Returns a counter object that can be used to track API calls.
    """
    class RequestCounter:
        def __init__(self):
            self.count = 0
            self.calls = []

        def increment(self, *args, **kwargs):
            self.count += 1
            self.calls.append({'args': args, 'kwargs': kwargs})

        def reset(self):
            self.count = 0
            self.calls = []

    return RequestCounter()


def create_mock_item(item_id, collection='wv02'):
    """
    Helper function to create a mock Item for testing.
    """
    mock_item = MagicMock()
    mock_item.id = item_id
    mock_item.collection = collection
    mock_item.properties = {'datetime': '2020-01-01T12:00:00Z'}
    mock_item.geometry = {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    mock_item.bbox = [0, 0, 1, 1]
    mock_item.assets = {}
    mock_item.links = []
    mock_item.type = 'Feature'
    return mock_item


def create_mock_item_collection(features, links=None):
    """
    Helper function to create a mock ItemCollection for testing.
    """
    mock_collection = MagicMock(spec=ItemCollection)
    mock_collection.features = features
    mock_collection.links = links
    mock_collection.type = 'FeatureCollection'
    return mock_collection
