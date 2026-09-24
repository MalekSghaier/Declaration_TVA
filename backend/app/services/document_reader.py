"""Lit un document (PDF natif, PDF scanne, image) et renvoie le texte page par page.

Regle : on n'utilise l'OCR (payant / limite) que pour les pages qui n'ont pas de vrai texte.
"""
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf  

from app.services import ocr

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
MIN_CHARS = 50          # en dessous : page consideree comme scannee
MIN_WORD_RATIO = 0.5    # part de "vrais mots" pour accepter une couche texte


@dataclass
class PageText:
    page: int      # commence a 0
    method: str    # "native", "ocr" ou "scan_non_lu"
    text: str


def _looks_like_real_text(text: str) -> bool:
    """Detecte les faux PDF natifs (couche texte illisible)."""
    tokens = re.findall(r"\S+", text)
    if len(text.strip()) < MIN_CHARS or not tokens:
        return False
    good = [t for t in tokens if re.search(r"[A-Za-z\u00C0-\u017F\u0600-\u06FF0-9]{2,}", t)]
    return len(good) / len(tokens) >= MIN_WORD_RATIO


def read_document(path: str, use_ocr: bool = True, force_ocr: bool = False) -> list[PageText]:
    p = Path(path)
    ext = p.suffix.lower()

    # Image : toujours OCR
    if ext in IMAGE_EXTENSIONS:
        if not use_ocr:
            return [PageText(0, "scan_non_lu", "")]
        return [PageText(0, "ocr", ocr.ocr_file(path)[0])]

    if ext != ".pdf":
        raise ValueError(f"Format non supporte : {ext}")

    # Force OCR sur tout le document (utile pour RNE/patente : bilingues + tableaux)
    if force_ocr:
        if not use_ocr:
            return [PageText(0, "scan_non_lu", "")]
        results = ocr.ocr_file(path)  # toutes les pages
        return [PageText(i, "ocr", results.get(i, "")) for i in sorted(results.keys())]

    # Sinon : logique actuelle (natif si possible, OCR en fallback)
    pages: list[PageText] = []
    to_ocr: list[int] = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if _looks_like_real_text(text):
                pages.append(PageText(i, "native", text))
            else:
                to_ocr.append(i)

    if to_ocr:
        if use_ocr:
            results = ocr.ocr_file(path, to_ocr)
            for i in to_ocr:
                pages.append(PageText(i, "ocr", results.get(i, "")))
        else:
            for i in to_ocr:
                pages.append(PageText(i, "scan_non_lu", ""))

    return sorted(pages, key=lambda x: x.page)