"""Comprehension du texte (LLM). Le texte peut venir du natif (PyMuPDF) ou de l'OCR."""
import re
import threading

from mistralai.client import Mistral
from pydantic import BaseModel

from app.config import settings
from app.services.document_reader import PageText
from app.services.schemas import InvoiceExtraction, PatenteExtraction, RNEExtraction

_client_singleton: Mistral | None = None
_client_lock = threading.Lock()


def _client() -> Mistral:
    global _client_singleton
    if _client_singleton is None:
        with _client_lock:
            if _client_singleton is None:
                _client_singleton = Mistral(
                    api_key=settings.MISTRAL_API_KEY.get_secret_value(),
                    server_url=settings.MISTRAL_BASE_URL,
                )
    return _client_singleton


# Les documents administratifs tunisiens (RNE, patente) sont bilingues francais/arabe,
# avec le meme contenu repete dans les deux langues. Le texte arabe n'apporte rien pour
# l'extraction (les champs qui nous interessent sont toujours donnes aussi en francais)
# et il noie le LLM sous du texte inutile, ce qui degrade la qualite d'extraction.
_ARABIC_RANGES = "\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF"
_ARABIC_RE = re.compile(f"[{_ARABIC_RANGES}]")


def _strip_arabic(text: str) -> str:
    cleaned = _ARABIC_RE.sub(" ", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def pages_to_text(pages: list[PageText]) -> str:
    joined = "\n\n".join(f"--- Page {p.page + 1} ---\n{p.text}" for p in pages)
    return _strip_arabic(joined)


def _extract(pages: list[PageText], schema: type[BaseModel], system: str) -> BaseModel:
    resp = _client().chat.parse(
        model=settings.MISTRAL_LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": pages_to_text(pages)},
        ],
        response_format=schema,
        temperature=0,
        max_tokens=2000,
    )
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        raise ValueError(
            "Reponse du LLM tronquee (limite de tokens atteinte) : augmentez max_tokens."
        )
    return choice.message.parsed


INVOICE_SYSTEM = """Tu extrais les donnees d'une facture tunisienne a partir de son texte (markdown).
Regles :
- Reponds uniquement selon le schema fourni.
- Montants en nombres avec point decimal (1234.500), sans separateur de milliers.
- Dates au format AAAA-MM-JJ.
- Si une information est absente ou illisible, mets null. N'invente jamais de valeur.
- Le matricule fiscal est recopie tel quel.
- Une ligne dans lignes_tva par taux de TVA distinct.
- Distingue bien l'emetteur (vendeur) du client."""

PATENTE_SYSTEM = """Tu extrais les informations d'une patente tunisienne (carte d'identification fiscale)
a partir de son texte. Le document original est bilingue francais/arabe ; le texte arabe a deja ete
retire, tu ne recois que la partie francaise.
Regles :
- Reponds uniquement selon le schema fourni.
- Cherche precisement les libelles suivants : "Matricule Fiscal", "Nom et prenom ou raison sociale",
  "Adresse", "Activite principal".
- Le matricule fiscal est recopie tel quel, avec ses lettres et chiffres (exemple : 1943273B).
- N'extrait qu'une seule adresse : celle de l'entreprise elle-meme (celle indiquee a cote de "Adresse"),
  jamais une adresse administrative appartenant a l'organisme emetteur du document.
- Si une information est absente ou illisible, mets null. N'invente jamais de valeur."""

RNE_SYSTEM = """Tu extrais les informations d'un extrait RNE (Registre National des Entreprises) tunisien
a partir de son texte. Le document original est bilingue francais/arabe ; le texte arabe a deja ete
retire, tu ne recois que la partie francaise.
Regles :
- Reponds uniquement selon le schema fourni.
- Cherche precisement les libelles suivants : "Denomination sociale", "Forme juridique", "Capital social",
  "Identifiant unique" (c'est le matricule fiscal), "Adresse du siege social", "Date de publication".
- capital : nombre uniquement, sans "DT" ni separateur de milliers (exemple : 150000).
- date_creation : utilise la "Date de publication" au format AAAA-MM-JJ si aucune autre date n'est indiquee.
- dirigeant : le nom de la personne indiquee dans le tableau "INFORMATIONS RELATIVES A LA DIRECTION".
- adresse : utilise UNIQUEMENT la ligne "Adresse du siege social". Ignore toute autre adresse presente
  dans le document, en particulier celle de l'organisme emetteur (Registre National des Entreprises,
  ses coordonnees postales en en-tete ou pied de page de chaque page). Ne concatene jamais plusieurs
  adresses : une seule valeur, ou null si aucune n'est clairement identifiable comme celle du siege social.
- Si une information est absente ou illisible, mets null. N'invente jamais de valeur."""


def extract_invoice(pages: list[PageText]) -> InvoiceExtraction:
    return _extract(pages, InvoiceExtraction, INVOICE_SYSTEM)


def extract_patente(pages: list[PageText]) -> PatenteExtraction:
    return _extract(pages[:2], PatenteExtraction, PATENTE_SYSTEM)  # 2 pages suffisent


def extract_rne(pages: list[PageText]) -> RNEExtraction:
    return _extract(pages[:2], RNEExtraction, RNE_SYSTEM)  # page 3 = mentions légales, inutile