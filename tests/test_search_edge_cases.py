#
# test_search_edge_cases.py
#
# Edge case tests for parameter validation, datetime ranges, and limit/page boundaries.
#

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from maxarcat import Catalog
from maxarcat.exceptions import CatalogError
from conftest import create_mock_item, create_mock_item_collection


class TestParameterValidation:
    """
    Tests for parameter validation in search() method.
    """

    def test_item_ids_with_string_is_accepted_as_sequence(self, mock_catalog):
        """
        Test that passing a string for item_ids is accepted because strings are sequences.
        Note: In Python, strings ARE sequences (they pass isinstance(s, abc.Sequence)).
        The code at lines 243-247 in catalog.py guards against non-sequences, but strings
        will pass this check. Each character becomes an ID in the list.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(item_ids='abc')

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['ids'] == ['a', 'b', 'c']

    def test_item_ids_with_integer_raises_error(self, mock_catalog):
        """
        Test that passing an integer for item_ids raises CatalogError.
        """
        with pytest.raises(CatalogError) as exc_info:
            mock_catalog.search(item_ids=12345)

        assert 'item_ids must be a sequence' in str(exc_info.value)

    def test_item_ids_with_list_succeeds(self, mock_catalog):
        """
        Test that passing a list for item_ids works correctly.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(item_ids=['id1', 'id2', 'id3'])

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['ids'] == ['id1', 'id2', 'id3']

    def test_item_ids_with_tuple_succeeds(self, mock_catalog):
        """
        Test that passing a tuple for item_ids works correctly.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(item_ids=('id1', 'id2', 'id3'))

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['ids'] == ['id1', 'id2', 'id3']

    def test_item_ids_with_set_raises_error(self, mock_catalog):
        """
        Test that passing a set for item_ids raises CatalogError.
        Note: Sets are NOT sequences in Python's collections.abc.Sequence.
        """
        with pytest.raises(CatalogError) as exc_info:
            mock_catalog.search(item_ids={'id1', 'id2', 'id3'})

        assert 'item_ids must be a sequence' in str(exc_info.value)

    def test_empty_collections_list(self, mock_catalog):
        """
        Test that passing an empty collections list doesn't add collections to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(collections=[])

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'collections' not in body

    def test_empty_item_ids_list(self, mock_catalog):
        """
        Test that passing an empty item_ids list doesn't add ids to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(item_ids=[])

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'ids' not in body

    def test_none_collections(self, mock_catalog):
        """
        Test that passing None for collections doesn't add collections to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(collections=None)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'collections' not in body

    def test_none_bbox(self, mock_catalog):
        """
        Test that passing None for bbox doesn't add bbox to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(bbox=None)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'bbox' not in body

    def test_none_intersects(self, mock_catalog):
        """
        Test that passing None for intersects doesn't add intersects to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(intersects=None)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'intersects' not in body


class TestCompleteParameter:
    """
    Tests for the complete parameter in search() method.
    Per lines 261-264 in catalog.py.
    """

    def test_complete_true(self, mock_catalog):
        """
        Test that complete=True is correctly added to request body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(complete=True)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['complete'] is True

    def test_complete_false(self, mock_catalog):
        """
        Test that complete=False is correctly added to request body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(complete=False)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['complete'] is False

    def test_complete_none(self, mock_catalog):
        """
        Test that complete=None doesn't add complete to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(complete=None)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'complete' not in body

    def test_complete_truthy_value(self, mock_catalog):
        """
        Test that truthy values for complete are converted to True.
        Per line 262: complete_value = True if complete else False
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(complete=1)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['complete'] is True

    def test_complete_falsy_value(self, mock_catalog):
        """
        Test that falsy values for complete are converted to False.
        Per line 262: complete_value = True if complete else False
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(complete=0)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['complete'] is False


class TestDatetimeRanges:
    """
    Tests for datetime range handling in search() method.
    Per lines 230-241 in catalog.py.
    """

    def test_both_start_and_end_datetime(self, mock_catalog):
        """
        Test datetime formatting when both start and end are provided.
        Format: {start}/{end}
        """
        mock_response = create_mock_item_collection(features=[])
        start = datetime(2020, 1, 1, 0, 0, 0)
        end = datetime(2020, 12, 31, 23, 59, 59)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(start_datetime=start, end_datetime=end)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['datetime'] == '2020-01-01T00:00:00.000000Z/2020-12-31T23:59:59.000000Z'

    def test_start_datetime_only(self, mock_catalog):
        """
        Test datetime formatting when only start is provided.
        Format: {start}/..
        """
        mock_response = create_mock_item_collection(features=[])
        start = datetime(2020, 6, 15, 12, 30, 0)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(start_datetime=start)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['datetime'] == '2020-06-15T12:30:00.000000Z/..'

    def test_end_datetime_only(self, mock_catalog):
        """
        Test datetime formatting when only end is provided.
        Format: ../{end}
        """
        mock_response = create_mock_item_collection(features=[])
        end = datetime(2020, 3, 20, 8, 15, 30)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(end_datetime=end)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['datetime'] == '../2020-03-20T08:15:30.000000Z'

    def test_neither_datetime_provided(self, mock_catalog):
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

    def test_datetime_with_microseconds(self, mock_catalog):
        """
        Test that microseconds are preserved in datetime formatting.
        """
        mock_response = create_mock_item_collection(features=[])
        start = datetime(2020, 1, 1, 12, 30, 45, 123456)

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(start_datetime=start)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['datetime'] == '2020-01-01T12:30:45.123456Z/..'


class TestLimitAndPageBoundaries:
    """
    Tests for limit and page parameter boundaries in search() method.
    Per lines 255-260 in catalog.py.
    """

    def test_limit_zero(self, mock_catalog):
        """
        Test that limit=0 doesn't add limit to body (falsy value).
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(limit=0)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'limit' not in body

    def test_limit_one(self, mock_catalog):
        """
        Test that limit=1 is correctly added to request body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(limit=1)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['limit'] == 1

    def test_limit_none(self, mock_catalog):
        """
        Test that limit=None doesn't add limit to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(limit=None)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'limit' not in body

    def test_limit_large_value(self, mock_catalog):
        """
        Test that large limit values are correctly added to request body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(limit=10000)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['limit'] == 10000

    def test_page_zero(self, mock_catalog):
        """
        Test that page=0 doesn't add page to body (falsy value).
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(page=0)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'page' not in body

    def test_page_one(self, mock_catalog):
        """
        Test that page=1 is correctly added to request body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(page=1)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['page'] == 1

    def test_page_none(self, mock_catalog):
        """
        Test that page=None doesn't add page to body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(page=None)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'page' not in body

    def test_page_large_value(self, mock_catalog):
        """
        Test that large page values are correctly added to request body.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(page=1000)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['page'] == 1000

    def test_limit_and_page_combined(self, mock_catalog):
        """
        Test that limit and page can be used together.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(limit=50, page=3)

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body['limit'] == 50
            assert body['page'] == 3


class TestQueryMethodEdgeCases:
    """
    Edge case tests for the query() generator method.
    """

    def test_query_with_empty_first_page(self, mock_catalog):
        """
        Test that query() handles empty first page correctly.
        """
        empty_collection = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, 'search', return_value=empty_collection) as mock_search:
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 0
            assert mock_search.call_count == 1

    def test_query_passes_all_parameters(self, mock_catalog):
        """
        Test that query() passes all parameters to search().
        """
        empty_collection = create_mock_item_collection(features=[])
        start = datetime(2020, 1, 1)
        end = datetime(2020, 12, 31)

        with patch.object(mock_catalog, 'search', return_value=empty_collection) as mock_search:
            list(mock_catalog.query(
                collections=['wv02'],
                bbox=[-105, 40, -104, 41],
                intersects={'type': 'Point', 'coordinates': [0, 0]},
                start_datetime=start,
                end_datetime=end,
                item_ids=['id1', 'id2'],
                where='eo:cloud_cover < 20',
                orderby='datetime',
                limit=50
            ))

            mock_search.assert_called_once_with(
                collections=['wv02'],
                bbox=[-105, 40, -104, 41],
                intersects={'type': 'Point', 'coordinates': [0, 0]},
                start_datetime=start,
                end_datetime=end,
                item_ids=['id1', 'id2'],
                where='eo:cloud_cover < 20',
                orderby='datetime',
                limit=50,
                page=1
            )

    def test_query_does_not_pass_complete_parameter(self, mock_catalog):
        """
        Test that query() does not have a complete parameter.
        The query() method signature doesn't include complete.
        """
        empty_collection = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, 'search', return_value=empty_collection) as mock_search:
            list(mock_catalog.query(collections=['wv02']))

            call_kwargs = mock_search.call_args[1]
            assert 'complete' not in call_kwargs

    def test_query_yields_individual_features(self, mock_catalog):
        """
        Test that query() yields individual features, not collections.
        """
        items = [create_mock_item(f'item_{i}') for i in range(5)]
        collection = create_mock_item_collection(features=items)
        empty_collection = create_mock_item_collection(features=[])

        call_count = [0]
        def mock_search_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return collection
            return empty_collection

        with patch.object(mock_catalog, 'search', side_effect=mock_search_side_effect):
            results = list(mock_catalog.query(collections=['wv02']))

            assert len(results) == 5
            for i, result in enumerate(results):
                assert result.id == f'item_{i}'


class TestSearchMethodEdgeCases:
    """
    Edge case tests for the search() method.
    """

    def test_search_with_no_parameters(self, mock_catalog):
        """
        Test that search() works with no parameters.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search()

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert body == {}

    def test_search_with_empty_bbox(self, mock_catalog):
        """
        Test that search() handles empty bbox list.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(bbox=[])

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'bbox' not in body

    def test_search_with_empty_where(self, mock_catalog):
        """
        Test that search() handles empty where string.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(where='')

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'where' not in body

    def test_search_with_empty_orderby(self, mock_catalog):
        """
        Test that search() handles empty orderby string.
        """
        mock_response = create_mock_item_collection(features=[])

        with patch.object(mock_catalog, '_call_api', return_value=mock_response) as mock_call:
            mock_catalog.search(orderby='')

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args
            body = call_kwargs[1]['body']
            assert 'orderby' not in body
