"""Test d'extraction reelle (avec cle Mistral), via le meme code que l'application.

Usage depuis backend/ :
    python test_extraction.py rne "samples\\rne_sarl.pdf"
    python test_extraction.py patente "samples\\patente_sociétéSARL.pdf"
    python test_extraction.py rne "samples\\rne_sarl.pdf" --full   (affiche aussi le texte lu)
"""
import sys
import traceback

if len(sys.argv) < 3 or sys.argv[1] not in ("rne", "patente"):
    print('Usage : python test_extraction.py <rne|patente> "chemin\\fichier.pdf" [--full]')
    sys.exit(1)

kind = sys.argv[1]
path = sys.argv[2]
full = "--full" in sys.argv

from app.config import settings  # noqa: E402
from app.services.document_reader import read_document  # noqa: E402
from app.services.extraction import extract_patente, extract_rne, pages_to_text  # noqa: E402

print("=== Configuration ===")
print("Base URL SDK :", settings.MISTRAL_BASE_URL)
print("Modele OCR   :", settings.MISTRAL_OCR_MODEL)
print("Modele LLM   :", settings.MISTRAL_LLM_MODEL)
print("OCR_MOCK     :", settings.OCR_MOCK, "(ignore par ce script)")

print(f"\n=== 1. Lecture du document ({path}) ===")
try:
    pages = read_document(path, force_ocr=True)  # OCR autorise pour les pages sans texte
except Exception:
    print("ECHEC de la lecture / OCR :")
    traceback.print_exc()
    sys.exit(1)

for p in pages:
    print(f"[page {p.page + 1}] methode={p.method} caracteres={len(p.text)}")

if not any(p.text.strip() for p in pages):
    print("Aucun texte lisible : l'OCR n'a rien renvoye. Arret.")
    sys.exit(1)

if full:
    print("\n--- Texte envoye au LLM ---")
    print(pages_to_text(pages))
else:
    print("\n--- Debut du texte (600 car.) ---")
    print(pages_to_text(pages)[:600])

print(f"\n=== 2. Extraction LLM ({kind}) ===")
try:
    result = extract_patente(pages) if kind == "patente" else extract_rne(pages)
except Exception:
    print("ECHEC de l'extraction LLM :")
    traceback.print_exc()
    sys.exit(1)

print(result.model_dump_json(indent=2))