from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(default="ONBOARDING")  # ONBOARDING | LOCKED
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Renseigne lors de l'onboarding, verrouille ensuite
    raison_sociale: Mapped[str | None]
    matricule_fiscal: Mapped[str | None]
    adresse: Mapped[str | None]
    forme_juridique: Mapped[str | None]
    code_tva: Mapped[str | None]                
    code_categorie: Mapped[str | None]          
    capital: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    date_creation: Mapped[date | None] = mapped_column(Date)
    activite: Mapped[str | None]
    dirigeant: Mapped[str | None]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("company_id", "kind", name="uq_company_doc_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str]  # PATENTE | RNE (FACTURE plus tard, sans contrainte unique)
    minio_key: Mapped[str]
    filename: Mapped[str]
    sha256: Mapped[str]
    extracted_data: Mapped[dict | None] = mapped_column(JSON)
    processing_status: Mapped[str] = mapped_column(default="DONE")
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())