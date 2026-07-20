from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import DeclarativeBase

VALID_KINDS = {"kp", "contract", "schema", "other"}

class Base(DeclarativeBase):
    pass

class Artifact(Base):
    __tablename__ = "artifacts"

    # FK deal_id → deals(id) задан на уровне БД (миграция 008, artifacts_deal_id_fkey).
    # В ORM колонка без ForeignKey — таблица deals не в метаданных этого Base.
    id         = Column(Integer, primary_key=True, index=True)
    kind       = Column(String(32), nullable=False)
    title      = Column(String(300), nullable=False)
    url        = Column(Text, nullable=True)
    deal_id    = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "kind":       self.kind,
            "title":      self.title,
            "url":        self.url,
            "deal_id":    self.deal_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
