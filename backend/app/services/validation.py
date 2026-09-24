import re
from dataclasses import dataclass
from decimal import Decimal

from app.services.schemas import InvoiceExtraction

TAUX_VALIDES = {Decimal(x) for x in (0, 7, 13, 19)}
TOLERANCE = Decimal("0.005")
# A affiner avec vos vrais documents
MF_REGEX = re.compile(r"^\d{7}\s*[A-Z](\s*/\s*[A-Z]\s*/\s*[A-Z]\s*/\s*\d{3})?$")


@dataclass
class Issue:
    field: str
    message: str
    severity: str  # "error" ou "warning"


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def validate_invoice(inv: InvoiceExtraction) -> list[Issue]:
    issues: list[Issue] = []

    for field in ("numero", "date_facture", "total_ht", "total_tva", "total_ttc"):
        if getattr(inv, field) is None:
            issues.append(Issue(field, "champ manquant", "error"))

    if inv.total_ht is not None and inv.total_tva is not None and inv.total_ttc is not None:
        attendu = inv.total_ht + inv.total_tva + (inv.timbre or Decimal(0))
        if not _close(attendu, inv.total_ttc):
            issues.append(Issue("total_ttc", f"HT+TVA+timbre={attendu} != TTC={inv.total_ttc}", "error"))

    for l in inv.lignes_tva:
        if l.taux not in TAUX_VALIDES:
            issues.append(Issue("lignes_tva", f"taux invalide : {l.taux}", "error"))
        elif not _close(l.base_ht * l.taux / 100, l.montant_tva):
            issues.append(Issue("lignes_tva", f"base {l.base_ht} x {l.taux}% != {l.montant_tva}", "warning"))

    if inv.lignes_tva:
        if inv.total_tva is not None and not _close(sum(l.montant_tva for l in inv.lignes_tva), inv.total_tva):
            issues.append(Issue("total_tva", "somme des lignes != total TVA", "error"))
        if inv.total_ht is not None and not _close(sum(l.base_ht for l in inv.lignes_tva), inv.total_ht):
            issues.append(Issue("total_ht", "somme des bases != total HT", "warning"))

    for f in ("emetteur_mf", "client_mf"):
        v = getattr(inv, f)
        if v and not MF_REGEX.match(v.strip().upper()):
            issues.append(Issue(f, f"format de matricule fiscal douteux : {v}", "warning"))

    return issues