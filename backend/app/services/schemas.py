from datetime import date
from decimal import Decimal
from pydantic import BaseModel

# ATTENTION : les modeles envoyes a Mistral (chat.parse) ne doivent pas contenir de Decimal :
# son schema JSON contient une regex que Mistral refuse (erreur 400, code 3051).
# On utilise float pour le LLM, et on reconvertit en Decimal cote application.
# TODO factures : InvoiceExtraction/TvaLine ont le meme probleme, a passer en float avant de les utiliser.


class TvaLine(BaseModel):
    taux: Decimal            # 0, 7, 13 ou 19
    base_ht: Decimal
    montant_tva: Decimal


class InvoiceExtraction(BaseModel):
    numero: str | None = None
    date_facture: date | None = None
    emetteur_nom: str | None = None
    emetteur_mf: str | None = None
    client_nom: str | None = None
    client_mf: str | None = None
    lignes_tva: list[TvaLine] = []
    total_ht: Decimal | None = None
    total_tva: Decimal | None = None
    timbre: Decimal | None = None
    total_ttc: Decimal | None = None
    devise: str | None = None


class PatenteExtraction(BaseModel):
    raison_sociale: str | None = None
    matricule_fiscal: str | None = None
    adresse: str | None = None
    activite: str | None = None


class RNEExtraction(BaseModel):
    raison_sociale: str | None = None
    matricule_fiscal: str | None = None
    forme_juridique: str | None = None
    capital: float | None = None
    date_creation: date | None = None
    dirigeant: str | None = None
    adresse: str | None = None


class CompanyProfile(BaseModel):
    raison_sociale: str | None = None
    matricule_fiscal: str | None = None
    adresse: str | None = None
    forme_juridique: str | None = None
    capital: Decimal | None = None
    date_creation: date | None = None
    activite: str | None = None
    dirigeant: str | None = None