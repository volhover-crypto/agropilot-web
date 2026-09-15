# backend/artifacts/template_models.py -- §27/A5: шаблоны артефактов
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ArtifactTemplate(Base):
    __tablename__ = "artifact_templates"

    id              = Column(Integer, primary_key=True)
    code            = Column(String(32), unique=True, nullable=False)
    kind            = Column(String(32), nullable=False)
    title_template  = Column(String(300), nullable=False)
    body_template   = Column(Text, nullable=False)
    note            = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id, "code": self.code, "kind": self.kind,
            "title_template": self.title_template,
            "body_template": self.body_template,
            "note": self.note,
        }
