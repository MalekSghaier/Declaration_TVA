import hashlib
import logging
import mimetypes
import os
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Company, Document, User
from app.services.document_reader import read_document
from app.services.extraction import extract_patente, extract_rne
from app.services.schemas import CompanyProfile, PatenteExtraction, RNEExtraction

logger = logging.getLogger("app.onboarding")

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 Mo

# Donnees fictives utilisees uniquement quand OCR_MOCK=true
MOCK_PATENTE = PatenteExtraction(
    raison_sociale="SOCIETE EXEMPLE SARL",
    matricule_fiscal="1234567/A/M/000",
    adresse="12 Rue de la Liberte, 1002 Tunis",
    activite="Commerce de materiel informatique",
)
MOCK_RNE = RNEExtraction(
    raison_sociale="SOCIETE EXEMPLE",
    matricule_fiscal="1234567/A/M/000",
    forme_juridique="SARL",
    capital=10000.0,
    date_creation=date(2018, 5, 14),
    dirigeant="Ahmed Ben Salah",
    adresse="12 Rue de la Liberte, 1002 Tunis",
)


def _ensure_not_locked(company: Company) -> None:
    if company.status == "LOCKED":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Societe deja verrouillee")


def _service_error(kind: str, step: str, exc: Exception) -> HTTPException:
    """Log le detail technique complet, renvoie un message lisible a l'utilisateur."""
    logger.exception("[%s] echec de %s", kind, step)
    if "429" in str(exc):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{kind} : limite de requetes du service OCR atteinte, reessayez dans quelques minutes.",
        )
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        f"{kind} : echec de {step}. Reessayez, ou contactez le support si le probleme persiste.",
    )


def _extract_fields(raw: bytes, ext: str, kind: str) -> BaseModel:
    if settings.OCR_MOCK:
        logger.warning("[MOCK] extraction simulee pour %s", kind)
        return MOCK_PATENTE if kind == "PATENTE" else MOCK_RNE

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        pages = read_document(tmp_path, force_ocr=True)
    except Exception as exc:
        raise _service_error(kind, "la lecture du document", exc) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if not any(p.text.strip() for p in pages):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{kind} : aucun texte lisible dans le document. Verifiez le fichier.",
        )

    try:
        return extract_patente(pages) if kind == "PATENTE" else extract_rne(pages)
    except Exception as exc:
        raise _service_error(kind, "l'extraction des champs", exc) from exc


def _process(company_id: int, kind: str, upload: UploadFile, db: Session) -> BaseModel:
    """Stocke le fichier dans MinIO, l'OCRise si besoin, extrait les champs."""
    raw = upload.file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{kind} : fichier vide")
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{kind} : fichier trop volumineux (10 Mo max)")

    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{kind} : format non supporte (PDF, PNG ou JPG)")

    sha256 = hashlib.sha256(raw).hexdigest()
    key = f"{company_id}/{kind.lower()}{ext}"
    storage.upload_bytes(key, raw, upload.content_type or "application/octet-stream")

    extracted = _extract_fields(raw, ext, kind)

    doc = db.scalar(select(Document).where(Document.company_id == company_id, Document.kind == kind))
    if doc is None:
        doc = Document(company_id=company_id, kind=kind)
        db.add(doc)
    doc.minio_key = key
    doc.filename = upload.filename or f"{kind.lower()}{ext}"
    doc.sha256 = sha256
    doc.extracted_data = extracted.model_dump(mode="json")
    doc.processing_status = "DONE"

    return extracted


def _merge(patente: PatenteExtraction, rne: RNEExtraction) -> CompanyProfile:
    # Le LLM renvoie le capital en float (Decimal refuse par Mistral) : on reconvertit ici.
    capital = Decimal(str(rne.capital)) if rne.capital is not None else None
    return CompanyProfile(
        raison_sociale=rne.raison_sociale or patente.raison_sociale,
        matricule_fiscal=patente.matricule_fiscal or rne.matricule_fiscal,
        adresse=patente.adresse or rne.adresse,
        forme_juridique=rne.forme_juridique,
        capital=capital,
        date_creation=rne.date_creation,
        activite=patente.activite,
        dirigeant=rne.dirigeant,
        code_tva=patente.code_tva,
        code_categorie=patente.code_categorie
    )


@router.post("/upload", response_model=CompanyProfile)
def upload(
    patente: UploadFile = File(...),
    rne: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company = db.get(Company, user.company_id)
    _ensure_not_locked(company)

    patente_data = _process(user.company_id, "PATENTE", patente, db)
    rne_data = _process(user.company_id, "RNE", rne, db)
    db.commit()

    return _merge(patente_data, rne_data)


class ConfirmIn(BaseModel):
    raison_sociale: str
    matricule_fiscal: str
    adresse: str | None = None
    forme_juridique: str | None = None
    capital: Decimal | None = None
    date_creation: date | None = None
    activite: str | None = None
    dirigeant: str | None = None
    code_tva: str | None = None          
    code_categorie: str | None = None    
    code_tva: str | None = None          
    code_categorie: str | None = None    
    

@router.post("/confirm")
def confirm(data: ConfirmIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.get(Company, user.company_id)
    _ensure_not_locked(company)

    for field, value in data.model_dump().items():
        setattr(company, field, value)
    company.status = "LOCKED"
    company.locked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "LOCKED"}


@router.get("/document/{kind}/file")
def get_file(kind: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kind = kind.upper()
    if kind not in ("PATENTE", "RNE"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Type inconnu")
    doc = db.scalar(
        select(Document).where(Document.company_id == user.company_id, Document.kind == kind)
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document non trouve")
    media_type = mimetypes.guess_type(doc.filename)[0] or "application/octet-stream"
    return Response(content=storage.get_bytes(doc.minio_key), media_type=media_type)