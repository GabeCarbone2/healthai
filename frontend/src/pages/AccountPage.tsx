import { Activity, ShieldCheck, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";

import { deleteAccount } from "../api";
import { PrivacyNotice } from "../components/PrivacyNotice";
import type { PrivacyInfo, User } from "../types";

type Props = {
  user: User;
  privacy: PrivacyInfo;
  onDeleted: () => void;
};

export function AccountPage({ user, privacy, onDeleted }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function removeAccount(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await deleteAccount(password);
      onDeleted();
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

  return (
    <div className="page account-page">
      <header className="page-header">
        <div>
          <h1>Conta e privacidade</h1>
          <p>Controle dos seus dados e do histórico armazenado.</p>
        </div>
      </header>

      <section className="account-card">
        <ShieldCheck size={25} />
        <div>
          <h2>Aviso aceito</h2>
          <p>
            {user.name} · {user.email}
          </p>
          {user.crm && user.crm_uf && (
            <p>CRM {user.crm}/{user.crm_uf}</p>
          )}
          <PrivacyNotice info={privacy} />
        </div>
      </section>

      <section className="danger-zone">
        <h2>Excluir conta e dados</h2>
        <p>
          Exclui permanentemente sua conta, sessões e todos os resultados
          associados. Esta ação não pode ser desfeita.
        </p>

        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        {!confirming ? (
          <button type="button" onClick={() => setConfirming(true)}>
            <Trash2 size={16} />
            Excluir minha conta
          </button>
        ) : (
          <form onSubmit={removeAccount}>
            <label>
              <span>Confirme sua senha</span>
              <input
                type="password"
                autoComplete="current-password"
                minLength={8}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <label>
              <span>Digite EXCLUIR para confirmar</span>
              <input type="text" pattern="EXCLUIR" required />
            </label>
            <div>
              <button
                type="button"
                onClick={() => setConfirming(false)}
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
    </div>
  );
}
