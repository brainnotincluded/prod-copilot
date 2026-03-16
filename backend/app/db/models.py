
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
