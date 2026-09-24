import { useEffect, useState } from "react";
import { isAxiosError } from "axios";
import { api } from "./api";

interface CompanyInfo {
  raison_sociale: string | null;
  matricule_fiscal: string | null;
  adresse: string | null;
  forme_juridique: string | null;
  capital: string | number | null; // Decimal serialise en chaine par le backend
  date_creation: string | null;
  activite: string | null;
  dirigeant: string | null;
  locked_at: string | null;
}

type FieldKey = Exclude<keyof CompanyInfo, "locked_at">;

const FIELDS: { key: FieldKey; label: string }[] = [
  { key: "raison_sociale", label: "Raison sociale" },
  { key: "matricule_fiscal", label: "Matricule fiscal" },
  { key: "adresse", label: "Adresse" },
  { key: "forme_juridique", label: "Forme juridique" },
  { key: "capital", label: "Capital" },
  { key: "date_creation", label: "Date de création" },
  { key: "activite", label: "Activité" },
  { key: "dirigeant", label: "Dirigeant" },
];

function display(key: FieldKey, value: string | number | null): string {
  if (value === null || value === "") return "—";
  if (key === "capital") {
    return Number(value).toLocaleString("fr-FR", { minimumFractionDigits: 3 }) + " DT";
  }
  if (key === "date_creation") {
    const [y, m, d] = String(value).split("-");
    return `${d}/${m}/${y}`;
  }
  return String(value);
}

export default function Info() {
  const [info, setInfo] = useState<CompanyInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get<CompanyInfo>("/company/info")
      .then(({ data }) => {
        if (!cancelled) setInfo(data);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail = isAxiosError(err) ? err.response?.data?.detail : null;
        setError(typeof detail === "string" ? detail : "Impossible de charger les informations.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <h1 className="db-title">Informations de la société</h1>
      <p className="db-muted">
        Issues de la patente et du RNE, confirmées
        {info?.locked_at ? ` le ${new Date(info.locked_at).toLocaleDateString("fr-FR")}` : ""}.
        Elles ne sont plus modifiables.
      </p>

      {error && <p className="db-error">{error}</p>}
      {!info && !error && <p className="db-muted">Chargement…</p>}

      {info && (
        <div className="db-card">
          <dl className="db-fields">
            {FIELDS.map((f) => (
              <div key={f.key} style={{ display: "contents" }}>
                <dt>{f.label}</dt>
                <dd>{display(f.key, info[f.key])}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </>
  );
}