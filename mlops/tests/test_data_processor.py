from app.mcp.data_processor import process_data


class TestProcessData:
    def test_filter_eq(self):
        """Filter uses 'column' key and 'operator' key per _apply_filter."""
        data = [{"name": "A", "status": "active"}, {"name": "B", "status": "inactive"}]
        result = process_data(data, [{"type": "filter", "column": "status", "operator": "eq", "value": "active"}])
        assert isinstance(result, dict)
        assert result["row_count"] == 1
        assert result["data"][0]["status"] == "active"

    def test_filter_contains(self):
        data = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Alicia"}]
        result = process_data(data, [{"type": "filter", "column": "name", "operator": "contains", "value": "Ali"}])
        assert result["row_count"] == 2

    def test_sort(self):
        """Sort uses 'column' key per _apply_sort."""
        data = [{"name": "B", "val": 2}, {"name": "A", "val": 1}]
        result = process_data(data, [{"type": "sort", "column": "name"}])
        assert isinstance(result, dict)
        assert result["data"][0]["name"] == "A"

    def test_limit(self):
        """Limit uses 'n' key per _apply_limit."""
        data = [{"id": i} for i in range(100)]
        result = process_data(data, [{"type": "limit", "n": 5}])
        assert isinstance(result, dict)
        assert result["row_count"] == 5

    def test_select_columns(self):
        data = [{"a": 1, "b": 2, "c": 3}]
        result = process_data(data, [{"type": "select_columns", "columns": ["a", "b"]}])
        assert isinstance(result, dict)
        assert set(result["columns"]) == {"a", "b"}

    def test_empty_data(self):
        result = process_data([], [{"type": "sort", "column": "id"}])
        assert isinstance(result, dict)
        assert result["row_count"] == 0

    def test_transform_to_table(self):
        data = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        result = process_data(data, [{"type": "transform_to_table"}])
        assert isinstance(result, dict)
        assert "columns" in result
        assert "rows" in result
        assert result["total_rows"] == 2

    def test_dict_input_with_items_key(self):
        """Dict with 'items' key is unpacked by _to_dataframe."""
        data = {"items": [{"id": 1}, {"id": 2}]}
        result = process_data(data, [{"type": "limit", "n": 1}])
        assert isinstance(result, dict)
        assert result["row_count"] == 1

    def test_invalid_operation_type(self):
        data = [{"id": 1}]
        # Unknown operation type is warned but not crashed
        result = process_data(data, [{"type": "unknown_op"}])
        assert isinstance(result, dict)
        # Data should pass through unchanged
        assert result["row_count"] == 1

    def test_multiple_operations(self):
        data = [{"name": "B", "val": 2}, {"name": "A", "val": 1}, {"name": "C", "val": 3}]
        result = process_data(data, [
            {"type": "sort", "column": "val"},
            {"type": "limit", "n": 2},
        ])
        assert isinstance(result, dict)
        assert result["row_count"] == 2

    def test_no_operations(self):
        data = [{"id": 1}]
        result = process_data(data, [])
        assert result == {"data": data, "message": "No operations specified"}

    def test_aggregate_sum(self):
        data = [{"val": 10}, {"val": 20}, {"val": 30}]
        result = process_data(data, [{"type": "aggregate", "function": "sum", "column": "val"}])
        assert isinstance(result, dict)
        assert result["data"][0]["value"] == 60

    def test_group_by(self):
        data = [
            {"category": "A", "val": 1},
            {"category": "A", "val": 2},
            {"category": "B", "val": 3},
        ]
        result = process_data(data, [{"type": "group_by", "columns": ["category"]}])
        assert isinstance(result, dict)
        assert result["row_count"] == 2

    def test_filter_missing_column_passthrough(self):
        """Filtering on a nonexistent column should return data unchanged."""
        data = [{"name": "A"}, {"name": "B"}]
        result = process_data(data, [{"type": "filter", "column": "nonexistent", "operator": "eq", "value": "X"}])
        assert result["row_count"] == 2

    # --- Smart merge tests -----------------------------------------------

    def test_merge_specified_source(self):
        """Merge with an explicitly specified source that has the right column."""
        posts = [{"id": 1, "userId": 1, "title": "p1"}, {"id": 2, "userId": 2, "title": "p2"}]
        users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        step_results = {"2": users}
        result = process_data(
            posts,
            [{"type": "merge", "source": "2", "left_on": "userId", "right_on": "id", "how": "inner"}],
            step_results=step_results,
        )
        assert result["row_count"] == 2
        assert "name" in result["columns"]

    def test_merge_auto_scan_wrong_source(self):
        """When the LLM gives the wrong source number, auto-scan finds the right one."""
        posts = [{"id": 1, "userId": 1, "title": "p1"}]
        users = [{"id": 1, "name": "Alice"}]
        # Source "3" does not exist; users are under key "2"
        step_results = {"1": posts, "2": users}
        result = process_data(
            posts,
            [{"type": "merge", "source": "3", "left_on": "userId", "right_on": "id", "how": "inner"}],
            step_results=step_results,
        )
        # Should auto-find source "2" which has the 'id' column
        assert result["row_count"] == 1
        assert "name" in result["columns"]

    def test_merge_auto_scan_column_mismatch(self):
        """When the specified source exists but lacks the right_on column, scan others."""
        posts = [{"id": 1, "userId": 1, "title": "p1"}]
        comments = [{"postId": 1, "body": "c1"}]  # no 'id' column
        users = [{"id": 1, "name": "Alice"}]
        # LLM says source "1" but that's posts (same data); source "2" is comments (no 'id')
        # source "3" is users (has 'id')
        step_results = {"1": posts, "2": comments, "3": users}
        result = process_data(
            posts,
            [{"type": "merge", "source": "2", "left_on": "userId", "right_on": "id", "how": "inner"}],
            step_results=step_results,
        )
        assert result["row_count"] == 1
        assert "name" in result["columns"]

    def test_merge_no_extra_data(self):
        """Merge with no step_results returns data unchanged."""
        posts = [{"id": 1, "userId": 1, "title": "p1"}]
        result = process_data(
            posts,
            [{"type": "merge", "source": "2", "left_on": "userId", "right_on": "id"}],
            step_results=None,
        )
        assert result["row_count"] == 1
        assert "name" not in result["columns"]
