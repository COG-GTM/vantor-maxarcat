#
# test_search_pagination_unit.py
#
# Mock-based unit tests for search and pagination functionality.
#

from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

from maxarcat import Catalog
from maxarcat.exceptions import CatalogError
from conftest import create_mock_item, create_mock_item_collection


class TestQueryGeneratorPaginationLogic:
    """
    Tests for the query() generator method pagination logic.
    """

    def test_empty_result_set_stops_immediately(self, mock_catalog):
        """
        Test that query() stops immediately when first page returns 0 features.
        Per lines 289-293 in catalog.py: if not num_features, return.
        """
        empty_collection = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, 'search', return_value=empty_collection) as mock_search:
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 0
            assert mock_search.call_count == 1
            mock_search.assert_called_once_with(
                collections=['wv02'], bbox=None, intersects=None,
                start_datetime=None, end_datetime=None,
                item_ids=None, where=None, orderby=None,
                limit=None, page=1
            )

    def test_single_page_results(self, mock_catalog):
        """
        Test query() with results that fit in a single page (results < page size).
        Should make exactly 2 requests: one with results, one empty to confirm end.
        """
        items = [create_mock_item(f'item_{i}') for i in range(5)]
        page1_collection = create_mock_item_collection(features=items)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return page1_collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect) as mock_search:
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 5
            assert mock_search.call_count == 2

    def test_exact_page_boundary_triggers_extra_request(self, mock_catalog, request_counter):
        """
        Test that when total results = page size, query() makes an extra request.
        This documents the known bug mentioned in lines 279-280 of catalog.py:
        "Using this logic we make one more request than we have to."
        """
        page_size = 100
        items = [create_mock_item(f'item_{i}') for i in range(page_size)]
        full_page_collection = create_mock_item_collection(features=items)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            request_counter.increment(**kwargs)
            if call_count[0] == 1:
                return full_page_collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect) as mock_search:
            results = list(mock_catalog.query(collections=['wv02'], limit=page_size))

            assert len(results) == page_size
            assert mock_search.call_count == 2
            assert request_counter.count == 2

    def test_multi_page_results_without_duplicates(self, mock_catalog):
        """
        Test query() correctly handles multiple pages without returning duplicates.
        """
        page1_items = [create_mock_item(f'item_page1_{i}') for i in range(50)]
        page2_items = [create_mock_item(f'item_page2_{i}') for i in range(50)]
        page3_items = [create_mock_item(f'item_page3_{i}') for i in range(25)]

        page1_collection = create_mock_item_collection(features=page1_items)
        page2_collection = create_mock_item_collection(features=page2_items)
        page3_collection = create_mock_item_collection(features=page3_items)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return page1_collection
            elif call_count[0] == 2:
                return page2_collection
            elif call_count[0] == 3:
                return page3_collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect) as mock_search:
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 125
            result_ids = [r.id for r in results]
            assert len(result_ids) == len(set(result_ids))
            assert mock_search.call_count == 4

    def test_page_parameter_increments_correctly(self, mock_catalog):
        """
        Test that the page parameter increments correctly in the pagination loop.
        Per line 281 in catalog.py: page += 1.
        """
        page1_items = [create_mock_item(f'item_{i}') for i in range(10)]
        page2_items = [create_mock_item(f'item_{i}') for i in range(10, 20)]

        page1_collection = create_mock_item_collection(features=page1_items)
        page2_collection = create_mock_item_collection(features=page2_items)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        page_numbers = []
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            page_numbers.append(kwargs.get('page'))
            if call_count[0] == 1:
                return page1_collection
            elif call_count[0] == 2:
                return page2_collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect):
            list(mock_catalog.query(collections=['wv02']))

            assert page_numbers == [1, 2, 3]


class TestRequestBodyConstruction:
    """
    Tests for verifying correct JSON body structure in search() method.
    """

    def test_collections_parameter(self, mock_catalog):
        """Test that collections parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(collections=['wv01', 'wv02', 'wv03-vnir'])

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['collections'] == ['wv01', 'wv02', 'wv03-vnir']

    def test_bbox_parameter(self, mock_catalog):
        """Test that bbox parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(bbox=[-105, 40, -104, 41])

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['bbox'] == [-105, 40, -104, 41]

    def test_intersects_parameter(self, mock_catalog):
        """Test that intersects geometry parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])
        geometry = {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(intersects=geometry)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['intersects'] == geometry

    def test_item_ids_parameter(self, mock_catalog):
        """Test that item_ids parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(item_ids=['id1', 'id2', 'id3'])

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['ids'] == ['id1', 'id2', 'id3']

    def test_where_parameter(self, mock_catalog):
        """Test that where filter parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(where='eo:cloud_cover < 20')

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['where'] == 'eo:cloud_cover < 20'

    def test_orderby_parameter(self, mock_catalog):
        """Test that orderby parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(orderby='datetime DESC')

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['orderby'] == 'datetime DESC'

    def test_limit_parameter(self, mock_catalog):
        """Test that limit parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(limit=50)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['limit'] == 50

    def test_page_parameter(self, mock_catalog):
        """Test that page parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(page=5)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['page'] == 5

    def test_complete_parameter_true(self, mock_catalog):
        """Test that complete=True parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(complete=True)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['complete'] is True

    def test_complete_parameter_false(self, mock_catalog):
        """Test that complete=False parameter is correctly added to request body."""
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(complete=False)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['complete'] is False

    def test_all_parameters_combined(self, mock_catalog):
        """Test that all parameters are correctly combined in request body."""
        mock_response = create_mock_item_collection(features=[])
        start = datetime(2020, 1, 1, 12, 0, 0)
        end = datetime(2020, 1, 2, 12, 0, 0)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(
                collections=['wv02'],
                bbox=[-105, 40, -104, 41],
                start_datetime=start,
                end_datetime=end,
                where='eo:cloud_cover < 20',
                orderby='datetime',
                limit=100,
                page=1,
                complete=True
            )

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['collections'] == ['wv02']
            assert body['bbox'] == [-105, 40, -104, 41]
            assert 'datetime' in body
            assert body['where'] == 'eo:cloud_cover < 20'
            assert body['orderby'] == 'datetime'
            assert body['limit'] == 100
            assert body['page'] == 1
            assert body['complete'] is True


class TestDatetimeFormatting:
    """
    Tests for datetime formatting in search() method.
    Per lines 230-241 in catalog.py.
    """

    def test_datetime_both_start_and_end(self, mock_catalog):
        """
        Test datetime formatting when both start and end are provided.
        Format: {start}/{end}
        """
        mock_response = create_mock_item_collection(features=[])
        start = datetime(2020, 1, 1, 12, 30, 45, 123456)
        end = datetime(2020, 6, 15, 18, 45, 30, 654321)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(start_datetime=start, end_datetime=end)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            expected = '2020-01-01T12:30:45.123456Z/2020-06-15T18:45:30.654321Z'
            assert body['datetime'] == expected

    def test_datetime_start_only(self, mock_catalog):
        """
        Test datetime formatting when only start is provided.
        Format: {start}/..
        """
        mock_response = create_mock_item_collection(features=[])
        start = datetime(2020, 1, 1, 12, 0, 0)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(start_datetime=start)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            expected = '2020-01-01T12:00:00.000000Z/..'
            assert body['datetime'] == expected

    def test_datetime_end_only(self, mock_catalog):
        """
        Test datetime formatting when only end is provided.
        Format: ../{end}
        """
        mock_response = create_mock_item_collection(features=[])
        end = datetime(2020, 12, 31, 23, 59, 59)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(end_datetime=end)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            expected = '../2020-12-31T23:59:59.000000Z'
            assert body['datetime'] == expected

    def test_datetime_neither_provided(self, mock_catalog):
        """
        Test that datetime is not included when neither start nor end is provided.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search()

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'datetime' not in body


class TestLinksMetadataHandling:
    """
    Tests for links metadata in ItemCollection responses.
    Documents that current query() doesn't check for "next" link.
    """

    def test_response_includes_links_metadata(self, mock_catalog):
        """
        Test that ItemCollection responses can include links metadata.
        """
        items = [create_mock_item('item_1')]
        links = [{'rel': 'next', 'href': 'https://api.example.com/next'}]
        collection_with_links = create_mock_item_collection(features=items, links=links)

        with patch.object(mock_catalog, 'search', return_value=collection_with_links):
            result = mock_catalog.search(collections=['wv02'])

            assert result.links is not None
            assert len(result.links) == 1
            assert result.links[0]['rel'] == 'next'

    def test_query_does_not_check_next_link(self, mock_catalog):
        """
        Document that query() method does NOT check for "next" link to determine
        if more pages exist. This is unlike the example code in scripts/examples.py
        (lines 33-35) which does check for a "next" link.

        The current implementation makes one more request than necessary because
        it relies on getting an empty result set to stop pagination.
        """
        items = [create_mock_item(f'item_{i}') for i in range(10)]
        collection_without_next = create_mock_item_collection(features=items, links=None)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return collection_without_next
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect) as mock_search:
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 10
            assert mock_search.call_count == 2

    def test_query_ignores_next_link_when_present(self, mock_catalog):
        """
        Document that query() ignores the "next" link even when present.
        It continues to use page counting instead of following links.
        """
        items = [create_mock_item(f'item_{i}') for i in range(10)]
        links_with_next = [{'rel': 'next', 'href': 'https://api.example.com/next?page=2'}]
        collection_with_next = create_mock_item_collection(features=items, links=links_with_next)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return collection_with_next
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect) as mock_search:
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 10
            assert mock_search.call_count == 2
            mock_search.assert_any_call(
                collections=['wv02'], bbox=None, intersects=None,
                start_datetime=None, end_datetime=None,
                item_ids=None, where=None, orderby=None,
                limit=None, page=2
            )


class TestRequestCounting:
    """
    Tests for counting HTTP requests during pagination.
    Documents the "one extra request" bug.
    """

    def test_extra_request_bug_documented(self, mock_catalog, request_counter):
        """
        This test documents the known bug where query() makes one more request
        than necessary. Per lines 279-280 in catalog.py:
        "Using this logic we make one more request than we have to."

        When there are exactly N items that fit in one page, query() will:
        1. Request page 1 (returns N items)
        2. Request page 2 (returns 0 items) - THIS IS THE EXTRA REQUEST

        The efficient implementation (as shown in scripts/examples.py lines 33-35)
        would check the "next" link and stop if it's not present.
        """
        items = [create_mock_item(f'item_{i}') for i in range(50)]
        page1_collection = create_mock_item_collection(
            features=items,
            links=None
        )
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            request_counter.increment(**kwargs)
            if call_count[0] == 1:
                return page1_collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect):
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 50
            assert request_counter.count == 2

    def test_query_generator_is_lazy(self, mock_catalog):
        """
        Test that query() generator doesn't load all results into memory at once.
        It should only fetch pages as needed when iterating.
        """
        page1_items = [create_mock_item(f'item_{i}') for i in range(100)]
        page2_items = [create_mock_item(f'item_{i}') for i in range(100, 200)]

        page1_collection = create_mock_item_collection(features=page1_items)
        page2_collection = create_mock_item_collection(features=page2_items)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return page1_collection
            elif call_count[0] == 2:
                return page2_collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect) as mock_search:
            generator = mock_catalog.query(collections=['wv02'])

            assert mock_search.call_count == 0

            first_item = next(generator)
            assert first_item.id == 'item_0'
            assert mock_search.call_count == 1

            for i, item in enumerate(generator):
                if i >= 99:
                    break
            assert mock_search.call_count == 2

    def test_request_count_for_multi_page_query(self, mock_catalog, request_counter):
        """
        Test that request count is accurate for multi-page queries.
        For N pages of results, query() makes N+1 requests (due to the extra request bug).
        """
        page1_items = [create_mock_item(f'item_{i}') for i in range(100)]
        page2_items = [create_mock_item(f'item_{i}') for i in range(100, 200)]
        page3_items = [create_mock_item(f'item_{i}') for i in range(200, 250)]

        page1_collection = create_mock_item_collection(features=page1_items)
        page2_collection = create_mock_item_collection(features=page2_items)
        page3_collection = create_mock_item_collection(features=page3_items)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            request_counter.increment(**kwargs)
            if call_count[0] == 1:
                return page1_collection
            elif call_count[0] == 2:
                return page2_collection
            elif call_count[0] == 3:
                return page3_collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect):
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 250
            assert request_counter.count == 4
