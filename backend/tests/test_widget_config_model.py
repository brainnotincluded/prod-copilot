"""Tests for WidgetConfig model.

Covers: table structure, JSON columns, widget types.
"""

import pytest

from app.db.models import WidgetConfig


class TestWidgetConfigModel:
    """SQLAlchemy WidgetConfig model validation."""

    def test_table_name(self):
        assert WidgetConfig.__tablename__ == "widget_configs"

    def test_primary_key(self):
        pk_cols = [c for c in WidgetConfig.__table__.columns if c.primary_key]
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"

    def test_scenario_id_nullable(self):
        """scenario_id can be null (global widgets)."""
        col = WidgetConfig.__table__.columns["scenario_id"]
        assert col.nullable is True

    def test_required_columns(self):
        cols = {c.name: c for c in WidgetConfig.__table__.columns}
        assert cols["widget_type"].nullable is False
        assert cols["title"].nullable is False
        assert cols["data_source"].nullable is False

    def test_json_columns(self):
        """data_source, config, and position are JSON."""
        cols = {c.name: c for c in WidgetConfig.__table__.columns}
        assert str(cols["data_source"].type) == "JSON"
        assert str(cols["config"].type) == "JSON"
        assert str(cols["position"].type) == "JSON"
        assert cols["data_source"].nullable is False
        assert cols["config"].nullable is True
        assert cols["position"].nullable is True


class TestWidgetConfigTypes:
    """Widget type validation."""

    VALID_TYPES = ["kpi", "chart", "table", "card", "timeline"]

    def test_all_widget_types(self):
        """All documented widget types should be creatable."""
        for i, wtype in enumerate(self.VALID_TYPES):
            widget = WidgetConfig(
                id=i,
                widget_type=wtype,
                title=f"{wtype.title()} Widget",
                data_source={"endpoint_id": 1},
            )
            assert widget.widget_type == wtype

    def test_kpi_widget(self):
        widget = WidgetConfig(
            id=1,
            widget_type="kpi",
            title="Total Users",
            data_source={"endpoint_id": 1, "field": "count"},
            config={"format": "number", "prefix": ""},
        )
        assert widget.config["format"] == "number"

    def test_chart_widget(self):
        widget = WidgetConfig(
            id=1,
            widget_type="chart",
            title="Revenue Trend",
            data_source={"endpoint_id": 2},
            config={"chart_type": "line", "x_axis": "date", "y_axis": "revenue"},
            position={"x": 0, "y": 0, "w": 6, "h": 4},
        )
        assert widget.config["chart_type"] == "line"
        assert widget.position["w"] == 6

    def test_table_widget(self):
        widget = WidgetConfig(
            id=1,
            widget_type="table",
            title="User List",
            data_source={"endpoint_id": 3},
            config={"columns": ["id", "name", "email"]},
        )
        assert len(widget.config["columns"]) == 3


class TestWidgetDataSource:
    """Data source configuration tests."""

    def test_endpoint_reference(self):
        widget = WidgetConfig(
            id=1,
            widget_type="kpi",
            title="Test",
            data_source={"endpoint_id": 42, "field_mapping": {"value": "total"}},
        )
        assert widget.data_source["endpoint_id"] == 42

    def test_complex_data_source(self):
        widget = WidgetConfig(
            id=1,
            widget_type="chart",
            title="Complex Chart",
            data_source={
                "endpoint_id": 10,
                "parameters": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
                "transform": "aggregate",
            },
        )
        assert "parameters" in widget.data_source
