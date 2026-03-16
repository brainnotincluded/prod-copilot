"""MCP Data Processor: pandas-based data transformation and aggregation."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _to_dataframe(data: Any) -> pd.DataFrame:
    """Convert various data formats to a pandas DataFrame.

    Handles dicts, lists of dicts, lists of lists, and existing DataFrames.
    """
    if isinstance(data, pd.DataFrame):
        return data.copy()

    if isinstance(data, dict):
        # Check if it looks like a table: {"columns": [...], "rows": [...]}
        if "columns" in data and "rows" in data:
            return pd.DataFrame(data["rows"], columns=data["columns"])
        # Check if it's column-oriented: {"col1": [...], "col2": [...]}
        if data and all(isinstance(v, (list, tuple)) for v in data.values()):
            lengths = [len(v) for v in data.values()]
            if len(set(lengths)) == 1:
                # All same length — normal column-oriented dict
                return pd.DataFrame(data)
            else:
                # Different lengths — pick the longest list that contains dicts
                best_key = max(data.keys(), key=lambda k: len(data[k]) if isinstance(data[k], list) else 0)
                best = data[best_key]
                if best and isinstance(best[0], dict):
                    return pd.DataFrame(best)
                return pd.DataFrame({"value": best})
        # Check if values are lists of dicts (nested structure like {by_segment: [{...}], by_status: [{...}]})
        list_keys = [k for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if list_keys:
            # Use the first list of dicts found
            return pd.DataFrame(data[list_keys[0]])
        # Check if it has items/results/data key with a list
        for key in ("items", "results", "data", "records", "body"):
            if key in data and isinstance(data[key], list):
                return pd.DataFrame(data[key])
        # Single row
        return pd.DataFrame([data])

    if isinstance(data, list):
        if not data:
            return pd.DataFrame()
        if isinstance(data[0], dict):
            return pd.DataFrame(data)
        if isinstance(data[0], (list, tuple)):
            return pd.DataFrame(data)
        # List of scalars
        return pd.DataFrame({"value": data})

    raise ValueError(f"Cannot convert data of type {type(data).__name__} to DataFrame")


def _apply_filter(df: pd.DataFrame, operation: dict) -> pd.DataFrame:
    """Apply a filter operation to the DataFrame."""
    column = operation.get("column", "")
    operator = operation.get("operator", "eq")
    value = operation.get("value")

    if column not in df.columns:
        logger.warning("Filter column '%s' not found in DataFrame", column)
        return df

    col = df[column]

    if operator == "eq":
        return df[col == value]
    elif operator == "ne":
        return df[col != value]
    elif operator == "gt":
        return df[col > value]
    elif operator == "lt":
        return df[col < value]
    elif operator == "gte":
        return df[col >= value]
    elif operator == "lte":
        return df[col <= value]
    elif operator == "contains":
        return df[col.astype(str).str.contains(str(value), case=False, na=False)]
    elif operator == "in":
        if isinstance(value, list):
            return df[col.isin(value)]
        return df[col == value]
    else:
        logger.warning("Unknown filter operator: %s", operator)
        return df


def _apply_sort(df: pd.DataFrame, operation: dict) -> pd.DataFrame:
    """Apply a sort operation to the DataFrame."""
    column = operation.get("column", "")
    ascending = operation.get("ascending", True)

    if isinstance(column, list):
        # Multiple column sort
        valid_cols = [c for c in column if c in df.columns]
        if not valid_cols:
            return df
        asc = ascending if isinstance(ascending, list) else [ascending] * len(valid_cols)
        return df.sort_values(by=valid_cols, ascending=asc).reset_index(drop=True)

    if column not in df.columns:
        logger.warning("Sort column '%s' not found in DataFrame", column)
        return df

    return df.sort_values(by=column, ascending=ascending).reset_index(drop=True)


def _apply_group_by(df: pd.DataFrame, operation: dict) -> pd.DataFrame:
    """Apply a group_by operation with aggregations."""
    columns = operation.get("columns", [])
    aggregations = operation.get("aggregations", {})

    if not columns:
        return df

    valid_cols = [c for c in columns if c in df.columns]
    if not valid_cols:
        logger.warning("No valid group_by columns found")
        return df

    if not aggregations:
        # Default to count
        return df.groupby(valid_cols).size().reset_index(name="count")

    # Build aggregation dict
    agg_dict = {}
    for col, func in aggregations.items():
        if col in df.columns:
            agg_dict[col] = func

    if not agg_dict:
        return df.groupby(valid_cols).size().reset_index(name="count")

    return df.groupby(valid_cols).agg(agg_dict).reset_index()


def _apply_aggregate(df: pd.DataFrame, operation: dict) -> pd.DataFrame:
    """Apply a single aggregation function."""
    function = operation.get("function", "count")
    column = operation.get("column")

    if function == "count":
        if column and column in df.columns:
            result = df[column].count()
        else:
            result = len(df)
        return pd.DataFrame({"aggregate": [function], "value": [result]})

    if not column or column not in df.columns:
        logger.warning("Aggregate column '%s' not found", column)
        return df

    if function == "sum":
        val = df[column].sum()
    elif function == "mean":
        val = df[column].mean()
    elif function == "min":
        val = df[column].min()
    elif function == "max":
        val = df[column].max()
    else:
        logger.warning("Unknown aggregate function: %s", function)
        return df

    return pd.DataFrame({"aggregate": [function], "column": [column], "value": [val]})


def _apply_select_columns(df: pd.DataFrame, operation: dict) -> pd.DataFrame:
    """Select specific columns from the DataFrame."""
    columns = operation.get("columns", [])
    valid_cols = [c for c in columns if c in df.columns]
    if not valid_cols:
        logger.warning("No valid columns found for select_columns")
        return df
    return df[valid_cols]


def _apply_limit(df: pd.DataFrame, operation: dict) -> pd.DataFrame:
    """Limit the number of rows."""
    n = operation.get("n", 10)
    return df.head(n)


def _transform_to_table(df: pd.DataFrame, operation: dict) -> dict:
    """Transform DataFrame into a table format."""
    columns = operation.get("columns")
    if columns:
        valid_cols = [c for c in columns if c in df.columns]
        if valid_cols:
            df = df[valid_cols]

    return {
        "columns": df.columns.tolist(),
        "rows": df.values.tolist(),
        "total_rows": len(df),
    }


def _transform_to_chart_data(df: pd.DataFrame, operation: dict) -> dict:
    """Transform DataFrame into chart-compatible data."""
    x = operation.get("x", "")
    y = operation.get("y", "")
    chart_type = operation.get("chart_type", "bar")

    if x not in df.columns or y not in df.columns:
        available = df.columns.tolist()
        return {
            "error": f"Columns '{x}' or '{y}' not found. Available: {available}",
            "chart_type": chart_type,
        }

    return {
        "chart_type": chart_type,
        "labels": df[x].astype(str).tolist(),
        "datasets": [
            {
                "label": y,
                "data": df[y].tolist(),
            }
        ],
        "x_label": x,
        "y_label": y,
    }


def _extract_coordinates(df: pd.DataFrame, operation: dict) -> dict:
    """Extract geographic coordinates from the DataFrame."""
    lat_col = operation.get("lat_column", "latitude")
    lng_col = operation.get("lng_column", "longitude")
    label_col = operation.get("label_column", "name")

    if lat_col not in df.columns or lng_col not in df.columns:
        return {
            "error": f"Coordinate columns '{lat_col}' or '{lng_col}' not found",
            "available_columns": df.columns.tolist(),
        }

    points = []
    for _, row in df.iterrows():
        lat = row.get(lat_col)
        lng = row.get(lng_col)
        if pd.notna(lat) and pd.notna(lng):
            point: dict[str, int | float | str] = {
                "lat": float(lat),
                "lng": float(lng),
            }
            if label_col in df.columns and pd.notna(row.get(label_col)):
                point["label"] = str(row[label_col])
            points.append(point)

    return {
        "type": "FeatureCollection",
        "points": points,
        "count": len(points),
    }


def _apply_merge(df: pd.DataFrame, operation: dict, extra_data: dict | None = None) -> pd.DataFrame:
    """Merge (JOIN) the current DataFrame with another dataset from step_results.

    Smart source resolution:
    1. If ``source`` is specified and the candidate has ``right_on``, use it.
    2. Otherwise auto-scan ALL step_results for one that contains ``right_on``.
    3. If ``left_on`` is missing from the left DataFrame, try to infer a
       compatible join column (e.g. ``userId`` -> ``id``).
    """
    source = operation.get("source", "")  # step_results key, e.g. "1"
    left_on = operation.get("left_on", "")
    right_on = operation.get("right_on", "")
    how = operation.get("how", "inner")  # inner, left, right, outer

    if not extra_data:
        logger.warning("No step_results for merge")
        return df

    # --- resolve right DataFrame ----------------------------------------
    right_df: pd.DataFrame | None = None

    # 1) Try the explicitly specified source first
    if source and source in extra_data:
        try:
            candidate = _to_dataframe(extra_data[source])
            if right_on in candidate.columns:
                right_df = candidate
                logger.info("Merge: using specified source '%s'", source)
        except Exception:
            pass

    # 2) Auto-scan: find the step_result that has the right_on column AND
    #    brings new information (columns not already in the left DataFrame).
    #    This avoids accidentally joining a table with itself when both have
    #    the right_on column (e.g. posts.id and users.id).
    if right_df is None:
        left_cols = set(df.columns)
        best_candidate: tuple[str, pd.DataFrame] | None = None
        for key, val in extra_data.items():
            if key == source:
                continue  # already tried
            try:
                candidate = _to_dataframe(val)
                if right_on not in candidate.columns:
                    continue
                new_cols = set(candidate.columns) - left_cols
                # Prefer candidates that introduce new columns (different table)
                if new_cols:
                    right_df = candidate
                    logger.info(
                        "Merge: auto-found source '%s' with column '%s' "
                        "(brings new columns: %s)",
                        key, right_on, new_cols,
                    )
                    break
                elif best_candidate is None:
                    # Fallback: same columns but at least has right_on
                    best_candidate = (key, candidate)
            except Exception:
                continue

        if right_df is None and best_candidate is not None:
            right_df = best_candidate[1]
            logger.info(
                "Merge: fallback to source '%s' with column '%s'",
                best_candidate[0], right_on,
            )

    if right_df is None:
        logger.warning("Merge: no source has column '%s'", right_on)
        return df

    # --- resolve left_on -------------------------------------------------
    if left_on not in df.columns:
        # Try to auto-detect a compatible join column
        resolved = False
        # Common pattern: left has 'userId' and right_on is 'id', or vice-versa
        candidates = {right_on, right_on + "Id", right_on + "_id"}
        for col in df.columns:
            if col.lower().replace("_", "") in {c.lower().replace("_", "") for c in candidates}:
                logger.info(
                    "Merge: auto-resolved left_on '%s' -> '%s'", left_on, col,
                )
                left_on = col
                resolved = True
                break
        if not resolved:
            logger.warning(
                "Merge: left_on '%s' not in left DataFrame. Available: %s",
                left_on, df.columns.tolist(),
            )
            return df

    logger.info(
        "Merge: joining left(%d rows, cols=%s) on '%s' with right(%d rows, cols=%s) on '%s' how='%s'",
        len(df), df.columns.tolist(), left_on,
        len(right_df), right_df.columns.tolist(), right_on,
        how,
    )
    merged = df.merge(
        right_df,
        left_on=left_on,
        right_on=right_on,
        how=how,
        suffixes=("", "_joined"),
    )
    logger.info("Merge: result has %d rows, %d columns", len(merged), len(merged.columns))
    return merged


def process_data(data: Any, operations: list[dict], step_results: dict | None = None) -> dict:
    """Process data through a pipeline of operations.

    Args:
        data: Input data (dict, list, or DataFrame).
        operations: List of operation dicts. Each must have a "type" key.
        step_results: Optional dict of all step results for merge/join operations.

    Returns:
        Dict with processed data.
    """
    if not operations:
        return {"data": data, "message": "No operations specified"}

    try:
        df = _to_dataframe(data)
    except (ValueError, TypeError) as e:
        return {"error": f"Failed to convert data to DataFrame: {str(e)}"}

    if df.empty:
        return {"data": [], "columns": [], "row_count": 0, "message": "Empty dataset"}

    logger.info("Processing data: %d rows, %d columns, %d operations",
                len(df), len(df.columns), len(operations))

    result: dict | None = None

    for i, op in enumerate(operations):
        op_type = op.get("type", "")

        try:
            if op_type == "filter":
                df = _apply_filter(df, op)
            elif op_type == "sort":
                df = _apply_sort(df, op)
            elif op_type == "group_by":
                df = _apply_group_by(df, op)
            elif op_type == "aggregate":
                df = _apply_aggregate(df, op)
            elif op_type == "select_columns":
                df = _apply_select_columns(df, op)
            elif op_type == "limit":
                df = _apply_limit(df, op)
            elif op_type == "transform_to_table":
                result = _transform_to_table(df, op)
            elif op_type == "transform_to_chart_data":
                result = _transform_to_chart_data(df, op)
            elif op_type == "extract_coordinates":
                result = _extract_coordinates(df, op)
            elif op_type == "merge":
                df = _apply_merge(df, op, step_results)
            else:
                logger.warning("Unknown operation type at index %d: %s", i, op_type)

            logger.info(
                "Op %d/%d (%s): %d rows remaining, op=%s",
                i + 1, len(operations), op_type, len(df),
                {k: v for k, v in op.items() if k != "type"},
            )

        except Exception as e:
            logger.error("Error in operation %d (%s): %s", i, op_type, str(e))
            return {
                "error": f"Operation '{op_type}' at index {i} failed: {str(e)}",
                "partial_data": df.head(10).to_dict(orient="records"),
                "row_count": len(df),
            }

    # If a transform produced a specific result, return it
    if result is not None:
        return result

    # Default: convert DataFrame to records
    # Replace NaN/NaT with None for JSON serialization
    df = df.where(pd.notna(df), None)

    # Convert numpy types to native Python types
    records = df.to_dict(orient="records")
    clean_records = []
    for record in records:
        clean = {}
        for k, v in record.items():
            if isinstance(v, (np.integer,)):
                clean[k] = int(v)
            elif isinstance(v, (np.floating,)):
                clean[k] = float(v) if not np.isnan(v) else None
            elif isinstance(v, np.bool_):
                clean[k] = bool(v)
            else:
                clean[k] = v
        clean_records.append(clean)

    return {
        "data": clean_records,
        "columns": df.columns.tolist(),
        "row_count": len(df),
    }
