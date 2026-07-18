import { Activity, LogOut, ShieldCheck, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";

import { acceptPrivacyConsent, deleteAccount } from "../api";
import { PrivacyNotice } from "../components/PrivacyNotice";
import { PageFooter } from "../components/PageFooter";
import type { PrivacyInfo, User } from "../types";

type Props = {
  info: PrivacyInfo;
  onAccepted: (user: User) => void;
  onLogout: () => Promise<boolean>;
  onAccountDeleted: () => void;
};

export function PrivacyConsentPage({
  info,
  onAccepted,
  onLogout,
  onAccountDeleted,
}: Props) {
  const [accepted, setAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showDeletion, setShowDeletion] = useState(false);
  const [password, setPassword] = useState("");

  async function submitConsent(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      onAccepted(await acceptPrivacyConsent());
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível registrar o consentimento.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function removeAccount(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await deleteAccount(password);
      onAccountDeleted();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível excluir a conta.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function leave() {
    setLoading(true);
    setError("");
    if (await onLogout()) return;
    setError("Não foi possível encerrar a sessão.");
    setLoading(false);
  }

  return (
    <main className="privacy-consent-page">
      <section>
        <ShieldCheck size={34} />
        <h1>Aviso de privacidade</h1>
        <PrivacyNotice info={info} />

        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        {!showDeletion ? (
          <>
            <form onSubmit={submitConsent}>
              <label className="consent-check">
                <input
                  type="checkbox"
                  required
                  checked={accepted}
                  onChange={(event) => setAccepted(event.target.checked)}
                />
                <span>
                  Li o aviso e consinto com o tratamento descrito para usar o
                  HealthAI.
                </span>
              </label>
              <button
                type="submit"
                className="primary-button"
                disabled={loading || !accepted}
              >
                {loading ? <Activity size={17} /> : <ShieldCheck size={17} />}
                {loading ? "Registrando..." : "Aceitar e continuar"}
              </button>
            </form>
            <div className="privacy-secondary-actions">
              <button type="button" onClick={leave} disabled={loading}>
                <LogOut size={16} />
                Sair
              </button>
              <button type="button" onClick={() => setShowDeletion(true)}>
                <Trash2 size={16} />
                Excluir minha conta
              </button>
            </div>
          </>
        ) : (
          <form className="privacy-delete-form" onSubmit={removeAccount}>
            <p>
              Para excluir permanentemente a conta e os resultados, confirme
              sua senha.
            </p>
            <label>
              <span>Senha</span>
              <input
                type="password"
                autoComplete="current-password"
                minLength={8}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <div>
              <button
                type="button"
                onClick={() => setShowDeletion(false)}
                disabled={loading}
              >
                Cancelar
              </button>
              <button type="submit" disabled={loading}>
                {loading ? <Activity size={16} /> : <Trash2 size={16} />}
                {loading ? "Excluindo..." : "Excluir permanentemente"}
              </button>
            </div>
          </form>
        )}
      </section>
      <PageFooter contact={info.contact} variant="public" />
    </main>
  );
}
