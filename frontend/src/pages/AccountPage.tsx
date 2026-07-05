import {
  Activity,
  CheckCircle2,
  Clock3,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { deleteAccount, submitCrm } from "../api";
import { PrivacyNotice } from "../components/PrivacyNotice";
import type { PrivacyInfo, User } from "../types";

type Props = {
  user: User;
  privacy: PrivacyInfo;
  onDeleted: () => void;
  onUserUpdated: (user: User) => void;
};

const BRAZILIAN_STATES = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
  "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
  "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

export function AccountPage({
  user,
  privacy,
  onDeleted,
  onUserUpdated,
}: Props) {
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [crm, setCrm] = useState(user.crm ?? "");
  const [crmUf, setCrmUf] = useState(user.crm_uf ?? "");
  const [crmLoading, setCrmLoading] = useState(false);
  const [crmError, setCrmError] = useState("");

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

  async function saveCrm(event: FormEvent) {
    event.preventDefault();
    setCrmLoading(true);
    setCrmError("");
    try {
      onUserUpdated(await submitCrm(crm, crmUf));
    } catch (requestError) {
      setCrmError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível enviar o CRM.",
      );
    } finally {
      setCrmLoading(false);
    }
  }

  const canSubmitCrm = !user.crm || user.crm_status === "rejected";

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

      <section className={`crm-status-card ${user.crm_status ?? "missing"}`}>
        {user.crm_status === "approved" ? (
          <CheckCircle2 size={25} />
        ) : user.crm_status === "rejected" ? (
          <XCircle size={25} />
        ) : (
          <Clock3 size={25} />
        )}
        <div>
          <h2>
            {user.crm_status === "approved"
              ? "Cadastro profissional aprovado"
              : user.crm_status === "rejected"
                ? "Cadastro profissional rejeitado"
                : user.crm
                  ? "Verificação profissional pendente"
                  : "Complete seu cadastro profissional"}
          </h2>
          <p>
            {user.crm_status === "approved"
              ? "Seu acesso às funcionalidades clínicas está liberado."
              : user.crm_status === "rejected"
                ? user.crm_rejection_reason
                  ?? "Revise os dados informados e envie novamente."
                : user.crm
                  ? "Um administrador precisa verificar seu CRM antes de liberar as avaliações."
                  : "Informe CRM e UF para iniciar a análise manual."}
          </p>
          {user.crm && user.crm_uf && (
            <strong>CRM {user.crm}/{user.crm_uf}</strong>
          )}
          {canSubmitCrm && (
            <form className="crm-update-form" onSubmit={saveCrm}>
              <label>
                <span>CRM</span>
                <input
                  type="text"
                  inputMode="numeric"
                  minLength={1}
                  maxLength={10}
                  pattern="[0-9]{1,10}"
                  required
                  value={crm}
                  onChange={(event) =>
                    setCrm(event.target.value.replace(/\D/g, ""))
                  }
                />
              </label>
              <label>
                <span>UF do CRM</span>
                <select
                  required
                  value={crmUf}
                  onChange={(event) => setCrmUf(event.target.value)}
                >
                  <option value="" disabled>Selecione</option>
                  {BRAZILIAN_STATES.map((state) => (
                    <option key={state} value={state}>{state}</option>
                  ))}
                </select>
              </label>
              <button type="submit" disabled={crmLoading}>
                {crmLoading ? <Activity size={16} /> : <ShieldCheck size={16} />}
                {crmLoading ? "Enviando..." : "Enviar para análise"}
              </button>
            </form>
          )}
          {crmError && <div className="form-error" role="alert">{crmError}</div>}
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
