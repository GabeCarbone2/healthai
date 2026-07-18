import { Activity, FileCheck2, LogOut } from "lucide-react";
import { FormEvent, useState } from "react";

import { acceptTermsConsent } from "../api";
import { ErrorSummary } from "../components/ErrorSummary";
import { TermsDocument } from "../components/TermsDocument";
import type { PrivacyInfo, TermsInfo, User } from "../types";

type Props = {
  info: TermsInfo;
  privacy: PrivacyInfo;
  onAccepted: (user: User) => void;
  onLogout: () => Promise<boolean>;
};

export function TermsConsentPage({ info, privacy, onAccepted, onLogout }: Props) {
  const [accepted, setAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      onAccepted(await acceptTermsConsent());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível registrar o aceite.");
      setLoading(false);
    }
  }

  async function leave() {
    setLoading(true);
    if (await onLogout()) return;
    setError("Não foi possível encerrar a sessão.");
    setLoading(false);
  }

  return (
    <main className="terms-consent-page">
      <section>
        <header>
          <FileCheck2 size={30} />
          <div>
            <span className="page-eyebrow">Aceite necessário</span>
            <h1>Termos de Uso</h1>
            <p>Leia a versão vigente para continuar usando as avaliações.</p>
          </div>
        </header>
        <TermsDocument info={info} contact={privacy.contact} />
        {error && <ErrorSummary message={error} />}
        <form onSubmit={submit}>
          <label className="consent-check">
            <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
            <span>Li e aceito os Termos de Uso versão {info.version}.</span>
          </label>
          <div>
            <button type="button" className="secondary-button" onClick={leave} disabled={loading}>
              <LogOut size={16} /> Sair
            </button>
            <button type="submit" className="primary-button" disabled={!accepted || loading}>
              {loading ? <Activity size={16} className="spin" /> : <FileCheck2 size={16} />}
              {loading ? "Registrando..." : "Aceitar e continuar"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
