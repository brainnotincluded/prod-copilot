
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class SwaggerSource(Base):
    """API source from Swagger/OpenAPI spec."""

    __tablename__ = "swagger_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=True)
    raw_json = Column(Text, nullable=False)
    base_url = Column(String(2048), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    endpoints = relationship(
        "ApiEndpoint",
        back_populates="swagger_source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ApiEndpoint(Base):
    """Individual API endpoint parsed from swagger source."""

    __tablename__ = "api_endpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    swagger_source_id = Column(
        Integer,
        ForeignKey("swagger_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    method = Column(String(10), nullable=False)
    path = Column(String(2048), nullable=False)
    summary = Column(String(1024), nullable=True)
    description = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)
    request_body = Column(JSON, nullable=True)
    response_schema = Column(JSON, nullable=True)
    embedding = Column(Vector(384), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    swagger_source = relationship("SwaggerSource", back_populates="endpoints")


class User(Base):
    """Application user (analyst, admin, viewer)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="editor")  # viewer, editor, admin
    is_active = Column(Integer, nullable=False, default=1)  # 1=active, 0=disabled
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChatConversation(Base):
    """A chat conversation (dialog session)."""

    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    """A single message in a chat conversation."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)  # stored result (table, chart, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("ChatConversation", back_populates="messages")


class EntityRelation(Base):
    """Discovered relations between entities across different APIs.

    Example: User.id ↔ Order.user_id, Campaign.audience_id ↔ Audience.id
    """

    __tablename__ = "entity_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_endpoint_id = Column(
        Integer,
        ForeignKey("api_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_endpoint_id = Column(
        Integer,
        ForeignKey("api_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Relation type: one_to_many, many_to_one, many_to_many
    relation_type = Column(String(20), nullable=False, default="one_to_many")
    # Field mapping: {"source_field": "user_id", "target_field": "id"}
    field_mapping = Column(JSON, nullable=False)
    # Confidence score from LLM analysis (0.0-1.0)
    confidence = Column(String(10), nullable=False, default="0.8")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScenarioRun(Base):
    """Stored execution of a multi-step scenario (visual scenario + history)."""

    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String(64), nullable=False, index=True, unique=True)
    query = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="running")  # running, completed, error, cancelled
    # Visual graph representation
    graph_nodes = Column(JSON, nullable=True)  # [{"id": "step1", "type": "api_call", "label": "..."}]
    graph_edges = Column(JSON, nullable=True)  # [{"from": "step1", "to": "step2"}]
    # Summary for UI
    summary = Column(JSON, nullable=True)  # {"total_steps": 5, "completed": 3, "duration_ms": 4200}
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at = Column(DateTime(timezone=True), nullable=True)

    steps = relationship(
        "ScenarioStep",
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioStep.step_number",
    )


class ScenarioStep(Base):
    """Individual step in a scenario execution."""

    __tablename__ = "scenario_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(
        Integer,
        ForeignKey("scenario_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number = Column(Integer, nullable=False)
    action = Column(String(255), nullable=False)  # e.g., "api_call", "transform", "decision"
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, error, skipped
    # API call details
    endpoint_id = Column(
        Integer,
        ForeignKey("api_endpoints.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_payload = Column(JSON, nullable=True)
    response_data = Column(JSON, nullable=True)
    # Reasoning chain for UI transparency
    reasoning = Column(Text, nullable=True)  # Why this step was chosen
    alternatives = Column(JSON, nullable=True)  # Rejected alternatives with reasons
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    # Error info
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scenario = relationship("ScenarioRun", back_populates="steps")


class ActionConfirmation(Base):
    """Tracks confirmation of mutating actions (POST/PUT/DELETE/PATCH on external APIs).

    Every write action discovered during orchestration must be confirmed
    before execution.  Status transitions: pending → approved | rejected.
    """

    __tablename__ = "action_confirmations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    # Link to scenario step if part of a scenario
    scenario_step_id = Column(
        Integer,
        ForeignKey("scenario_steps.id", ondelete="CASCADE"),
        nullable=True,
    )
    action = Column(String(255), nullable=False)
    endpoint_method = Column(String(10), nullable=False)
    endpoint_path = Column(String(2048), nullable=False)
    payload_summary = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(255), nullable=True)


class WidgetConfig(Base):
    """Configuration for auto-generated UI widgets (KPIs, charts, tables).

    These are generated based on API response schemas and user query intent.
    """

    __tablename__ = "widget_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(
        Integer,
        ForeignKey("scenario_runs.id", ondelete="CASCADE"),
        nullable=True,
    )
    widget_type = Column(String(50), nullable=False)  # kpi, chart, table, card, timeline
    title = Column(String(255), nullable=False)
    # Data source configuration
    data_source = Column(JSON, nullable=False)  # {"endpoint_id": 123, "field_mapping": {...}}
    # UI configuration
    config = Column(JSON, nullable=True)  # Chart type, columns for table, etc.
    # Position in dashboard
    position = Column(JSON, nullable=True)  # {"x": 0, "y": 0, "w": 6, "h": 4}
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
