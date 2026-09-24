import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { isAxiosError } from "axios";
import { useAuth } from "./AuthContext";
import "./Login.css";

export default function Login() {
  const { user, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await (mode === "login" ? login : register)(email, password);
    } catch (err) {
      const detail = isAxiosError(err) ? err.response?.data?.detail : null;
      setError(
        typeof detail === "string"
          ? detail
          : "Vérifiez vos informations (mot de passe : 8 caractères minimum)."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <aside className="auth-brand">
        <span className="auth-brand-mark">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="1" width="12" height="12" stroke="#f7f4ec" strokeWidth="1.2" />
            <rect x="5" y="5" width="4" height="4" fill="#4f8c7a" />
          </svg>
          Déclaration TVA
        </span>

        <div className="auth-brand-copy">
          <h2>Vos déclarations mensuelles, sans ressaisie.</h2>
          <p>Importez vos factures, l'extraction fait le reste.</p>
        </div>

        <svg className="auth-stamp" viewBox="0 0 200 200" aria-hidden="true">
          <defs>
            <path id="stampArcTop" d="M 30,100 A 70,70 0 1,1 170,100" />
          </defs>
          <circle className="stamp-ring-outer" cx="100" cy="100" r="88" pathLength="100" />
          <circle className="stamp-ring-inner" cx="100" cy="100" r="70" pathLength="100" />
          <text>
            <textPath href="#stampArcTop" startOffset="50%" textAnchor="middle">
              DÉCLARATION · MENSUELLE
            </textPath>
          </text>
          <text className="stamp-center" x="100" y="112">
            TVA
          </text>
        </svg>
      </aside>

      <div className="auth-panel">
        <div className="auth-card">
          <form onSubmit={onSubmit} className="auth-form">
            <h1>{mode === "login" ? "Connexion" : "Créer un compte"}</h1>

            <div className="auth-fields">
              <div className="auth-field">
                <label htmlFor="email">Email</label>
                <div className="auth-input-wrap">
                  <input
                    id="email"
                    type="email"
                    placeholder="vous@societe.tn"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="auth-field">
                <label htmlFor="password">Mot de passe</label>
                <div className="auth-input-wrap">
                  <input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>

            {error && <p className="auth-error">{error}</p>}

            <button className="auth-submit" disabled={busy}>
              {mode === "login" ? "Se connecter" : "S'inscrire"}
            </button>

            <button
              type="button"
              className="auth-switch"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Pas de compte ? S'inscrire" : "Déjà un compte ? Se connecter"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}