from sqlalchemy import Column, Integer, String, Text, BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


VALID_KINDS = {"kp", "contract", "schema", "other"}


class Artifact(Base):
    __tablename__ = "artifacts"

    id         = Column(Integer, primary_key=True, index=True)
    kind       = Column(String(32), nullable=False)
    title      = Column(String(300), nullable=False)
    url        = Column(Text, nullable=True)
    deal_id    = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    blob_uri   = Column(Text, nullable=True)
    filename   = Column(String(300), nullable=True)
    ext        = Column(String(16), nullable=True)
    mime       = Column(String(128), nullable=True)
    size       = Column(BigInteger, nullable=True)
    type       = Column(String(32), nullable=True)
    status     = Column(String(16), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "url": self.url,
            "deal_id": self.deal_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "date": self.created_at.isoformat() if self.created_at else None,
            "blob_uri": self.blob_uri,
            "filename": self.filename,
            "ext": self.ext,
            "mime": self.mime,
            "size": self.size,
            "type": self.type,
            "status": self.status,
        }
