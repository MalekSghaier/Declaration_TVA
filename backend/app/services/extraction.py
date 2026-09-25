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


# ---------------------------------------------------------------------------
# Nettoyage du texte avant envoi au LLM
# ---------------------------------------------------------------------------
# Les documents RNE sont emis par un organisme unique avec un pied de page
# standardise qui revient sur CHAQUE page. Ce bruit pollue le LLM et peut etre
# confondu avec les donnees metier (ex: adresse de l'organisme prise pour
# l'adresse du siege). On le retire.
#
# IMPORTANT : on NE retire PAS l'arabe. Certaines donnees (ex: nom du dirigeant)
# peuvent n'exister qu'en version arabe. Le LLM Mistral gere le bilingue.

_NOISE_PATTERNS = [
    # Coordonnees de l'organisme emetteur (RNE / structure fiscale)
    r"registre-entreprises\.tn[^\s]*",
    r"https?://\S+",
    r"contact@registre-entreprises\.tn",
    r"www\.registre-entreprises\.tn",
    r"\+216[\s\d]+",
    # Adresse du RNE en pied de page (version francaise et arabe)
    r"N°1\s+Rue\s+LAC\s+TOBA[^\n]*",
    r"صافي\s+1\s+عدد\s+LAC\s+TOBA[^\n]*",
    # Lignes purement decoratives (QR codes vides, separateurs)
    r"\[\s*\]\([^)]+\)",
]


def _strip_noise(text: str) -> str:
    for pat in _NOISE_PATTERNS:
        text = re.sub(pat, " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def pages_to_text(pages: list[PageText]) -> str:
    joined = "\n\n".join(f"--- Page {p.page + 1} ---\n{p.text}" for p in pages)
    return _strip_noise(joined)


def _extract(pages: list[PageText], schema: type[BaseModel], system: str) -> BaseModel:
    resp = _client().chat.parse(
        model=settings.MISTRAL_LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": pages_to_text(pages)},
        ],
        response_format=schema,
        temperature=0,
    )
    return resp.choices[0].message.parsed


# ---------------------------------------------------------------------------
# Prompts systeme
# ---------------------------------------------------------------------------
# Tous les RNE sont emis par le meme organisme, tous les patentes aussi.
# On cible donc les libelles francais qui sont constants sur tous les documents,
# ainsi que les pieges qui sont constants eux aussi.

INVOICE_SYSTEM = """Tu extrais les donnees d'une facture tunisienne a partir de son texte (markdown).
Regles :
- Reponds uniquement selon le schema fourni.
- Montants en nombres avec point decimal (1234.500), sans separateur de milliers.
- Dates au format AAAA-MM-JJ.
- Si une information est absente ou illisible, mets null. N'invente jamais de valeur.
- Le matricule fiscal est recopie tel quel.
- Une ligne dans lignes_tva par taux de TVA distinct.
- Distingue bien l'emetteur (vendeur) du client."""


PATENTE_SYSTEM = """Tu extrais les informations d'une carte d'identification fiscale tunisienne (patente)
a partir de son texte. La patente est emise par la Direction Generale des Impots avec un template
standard. Le document est bilingue francais/arabe.

Libelles francais presents sur toutes les patentes (cherche ces chaines exactes) :
- "Matricule Fiscal"      -> matricule_fiscal
- "Nom et prenom ou raison sociale" -> raison_sociale
- "Adresse"               -> adresse
- "Activite principal"    -> activite

PIEGES :
- "Code TVA", "Code Categorie", "N° etablissement secondaire" ne sont PAS le matricule fiscal.
- Le champ "Nom et prenom ou raison sociale" peut etre VIDE sur certaines patentes (personne
  physique dont le nom figure sur une autre ligne). Si tu ne trouves pas de valeur claire, mets null.
- La patente comporte un cachet bleu (image) et des zones arabes. Ignore-les.
- L'adresse figure sur 2-3 lignes consecutives : reconstitue-la en une seule chaine.

Regles finales :
- Reponds uniquement selon le schema fourni.
- N'invente jamais de valeur. Si tu n'es pas certain a 90%, mets null."""


RNE_SYSTEM = """Tu extrais les informations d'un extrait RNE (Registre National des Entreprises) tunisien.

Le RNE est emis par un organisme unique avec un template standard. Tous les extraits partagent :
- Les MEMES libelles francais : "Denomination sociale", "IDENTIFIANT UNIQUE", "Forme juridique",
  "Capital social", "Adresse du siege social", "Date de publication", "NOM ET PRENOM".
- La MEME structure : page 1 = identification, page 2 = direction + mentions, page 3 = mentions legales.
- Le MEME pied de page : coordonnees du RNE (registre-entreprises.tn, +216 70 248 170, etc.).

Le document est bilingue francais/arabe. Utilise la version francaise quand elle existe,
la version arabe UNIQUEMENT quand c'est la seule source (cas typique : nom du dirigeant).

TYPES DE RNE POSSIBLES :
- "EXTRAIT RNE (SOCIETE)" : a forme_juridique + capital + dirigeant.
- "EXTRAIT RNE (ENTREPRISE INDIVIDUELLE)" : PAS de forme juridique, PAS de capital,
  le "dirigeant" est l'exploitant lui-meme.

PIEGES A EVITER ABSOLUMENT (valables pour TOUS les RNE) :
1. "NUMERO EXTRAIT" (format ER + chiffres) n'est PAS le matricule fiscal.
2. "N° DE GESTION INTERNE" (format B + chiffres) n'est PAS le matricule fiscal.
3. "DATE D'EDITION DE L'EXTRAIT" n'est PAS la date de creation - c'est la date d'impression.
4. L'adresse "N°1 Rue LAC TOBA les Berges du Lac 1 -1053- Tunis" est celle du RNE,
   PAS celle de la societe. Elle apparait en pied de page de chaque page. IGNORE-LA.
5. Ne concatene JAMAIS plusieurs adresses. Une seule valeur.
6. Si plusieurs dirigeants, garde UNIQUEMENT le premier (gerant ou president) et ignore
   les autres ainsi que les commissaires aux comptes.
7. Si le nom du dirigeant est en arabe, translittere-le en caracteres latins.

Regles finales :
- Reponds uniquement selon le schema fourni.
- N'invente jamais de valeur. Si tu n'es pas certain a 90%, mets null."""


def extract_invoice(pages: list[PageText]) -> InvoiceExtraction:
    return _extract(pages, InvoiceExtraction, INVOICE_SYSTEM)


def extract_patente(pages: list[PageText]) -> PatenteExtraction:
    return _extract(pages, PatenteExtraction, PATENTE_SYSTEM)


def extract_rne(pages: list[PageText]) -> RNEExtraction:
    # Page 3 = mentions legales, on la garde si elle existe mais le LLM saura l'ignorer.
    return _extract(pages, RNEExtraction, RNE_SYSTEM)