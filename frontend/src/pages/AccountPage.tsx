import {
  Activity,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  EyeOff,
  ShieldCheck,
  Trash2,
  UserRound,
  XCircle,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { deleteAccount, submitCrm } from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorSummary } from "../components/ErrorSummary";
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

function maskEmail(email: string) {
  const [local, domain] = email.split("@");
  return `${local.slice(0, 2)}${"•".repeat(Math.max(3, local.length - 2))}@${domain}`;
}

function maskCrm(crm: string) {
  return `${"•".repeat(Math.max(2, crm.length - 2))}${crm.slice(-2)}`;
}

function formatDate(value: string | null) {
  if (!value) return "Data não registrada";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "long" }).format(new Date(value));
}

export function AccountPage({
  user,
  privacy,
  onDeleted,
  onUserUpdated,
}: Props) {
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showData, setShowData] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [crm, setCrm] = useState(user.crm ?? "");
  const [crmUf, setCrmUf] = useState(user.crm_uf ?? "");
  const [crmLoading, setCrmLoading] = useState(false);
  const [crmError, setCrmError] = useState("");

  async function removeAccount() {
    if (confirmation !== "EXCLUIR" || password.length < 8) return;
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

  function closeDeletion() {
    if (loading) return;
    setConfirming(false);
    setPassword("");
    setConfirmation("");
    setError("");
  }

  const canSubmitCrm = !user.crm || user.crm_status === "rejected";

  return (
    <div className="page account-page">
      <header className="page-header">
        <div>
          <span className="page-eyebrow">Controle e transparência</span>
          <h1>Conta e privacidade</h1>
          <p>Consulte dados armazenados, direitos e status do acesso profissional.</p>
        </div>
      </header>

      <div className="account-grid">
        <section className="account-card account-data-card">
          <header>
            <UserRound size={22} aria-hidden="true" />
            <div>
              <h2>Dados da conta</h2>
              <p>Dados usados para autenticação e análise do cadastro.</p>
            </div>
            <button type="button" className="show-data-button" onClick={() => setShowData((current) => !current)}>
              {showData ? <EyeOff size={16} /> : <Eye size={16} />}
              {showData ? "Ocultar dados" : "Mostrar dados"}
            </button>
          </header>
          <dl className="account-data-list">
            <div><dt>Nome</dt><dd>{showData ? user.name : `${user.name.slice(0, 1)}••••••`}</dd></div>
            <div><dt>E-mail</dt><dd>{showData ? user.email : maskEmail(user.email)}</dd></div>
            <div><dt>CRM</dt><dd>{user.crm && user.crm_uf ? `${showData ? user.crm : maskCrm(user.crm)}/${user.crm_uf}` : "Não informado"}</dd></div>
            <div><dt>Aviso aceito</dt><dd>{user.privacy_notice_version ?? "Pendente"}</dd></div>
            <div><dt>Termos aceitos</dt><dd>{user.terms_version ?? "Pendente"}</dd></div>
          </dl>
        </section>

        <section className="account-card storage-card">
          <header>
            <Database size={22} aria-hidden="true" />
            <div>
              <h2>Dados das avaliações</h2>
              <p>O que fica armazenado por até {privacy.result_retention_days} dias.</p>
            </div>
          </header>
          <div className="storage-columns">
            <div>
              <h3>Armazenado</h3>
              <ul>
                <li>Identificador pseudonimizado</li>
                <li>Resultado, probabilidade e limiar</li>
                <li>Modelo, versão e completude</li>
              </ul>
            </div>
            <div>
              <h3>Não armazenado</h3>
              <ul>
                <li>Nome, CPF ou prontuário do paciente</li>
                <li>Valores clínicos enviados ao cálculo</li>
                <li>Tabela externa que liga código à pessoa</li>
              </ul>
            </div>
          </div>
        </section>
      </div>

      <section className={`crm-status-card ${user.crm_status ?? "missing"}`}>
        {user.crm_status === "approved" ? (
          <CheckCircle2 size={25} />
        ) : user.crm_status === "rejected" ? (
          <XCircle size={25} />
        ) : (
          <Clock3 size={25} />
        )}
        <div>
          <span className="status-kicker">Análise manual do cadastro</span>
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
              ? `Aprovação administrativa registrada em ${formatDate(user.crm_verified_at)}.`
              : user.crm_status === "rejected"
                ? user.crm_rejection_reason ?? "Revise os dados informados e envie novamente."
                : user.crm
                  ? "Um administrador precisa analisar manualmente os dados antes de liberar as avaliações."
                  : "Informe CRM e UF para iniciar a análise manual."}
          </p>
          {user.crm && user.crm_uf && <strong>CRM {showData ? user.crm : maskCrm(user.crm)}/{user.crm_uf}</strong>}
          {canSubmitCrm && (
            <form className="crm-update-form" onSubmit={saveCrm}>
              <label htmlFor="account-crm">
                <span>CRM</span>
                <input
                  id="account-crm"
                  type="text"
                  inputMode="numeric"
                  minLength={1}
                  maxLength={10}
                  pattern="[0-9]{1,10}"
                  required
                  value={crm}
                  onChange={(event) => setCrm(event.target.value.replace(/\D/g, ""))}
                />
              </label>
              <label htmlFor="account-crm-uf">
                <span>UF do CRM</span>
                <select id="account-crm-uf" required value={crmUf} onChange={(event) => setCrmUf(event.target.value)}>
                  <option value="" disabled>Selecione</option>
                  {BRAZILIAN_STATES.map((state) => <option key={state} value={state}>{state}</option>)}
                </select>
              </label>
              <button type="submit" disabled={crmLoading}>
                {crmLoading ? <Activity size={16} /> : <ShieldCheck size={16} />}
                {crmLoading ? "Enviando..." : "Enviar para análise"}
              </button>
            </form>
          )}
          {crmError && <ErrorSummary title="Não foi possível enviar" message={crmError} />}
        </div>
      </section>

      <section className="privacy-card">
        <header>
          <ShieldCheck size={23} aria-hidden="true" />
          <div>
            <h2>Privacidade e direitos</h2>
            <p>Resumo do aviso aceito e canais disponíveis.</p>
          </div>
        </header>
        <PrivacyNotice info={privacy} />
      </section>

      <section className="danger-zone">
        <div>
          <h2>Excluir conta e dados</h2>
          <p>Exclui permanentemente conta, sessões e resultados associados.</p>
        </div>
        <button type="button" onClick={() => setConfirming(true)}>
          <Trash2 size={16} />
          Excluir minha conta
        </button>
      </section>

      <ConfirmDialog
        open={confirming}
        title="Excluir conta permanentemente?"
        description="Esta ação apaga sua conta, sessões e resultados e não pode ser desfeita."
        confirmLabel="Excluir permanentemente"
        busyLabel="Excluindo..."
        busy={loading}
        confirmDisabled={password.length < 8 || confirmation !== "EXCLUIR"}
        onCancel={closeDeletion}
        onConfirm={removeAccount}
      >
        <div className="dialog-form">
          <label htmlFor="delete-account-password">
            <span>Confirme sua senha</span>
            <input
              id="delete-account-password"
              type="password"
              autoComplete="current-password"
              minLength={8}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <label htmlFor="delete-account-confirmation">
            <span>Digite EXCLUIR para confirmar</span>
            <input
              id="delete-account-confirmation"
              type="text"
              autoComplete="off"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value.toUpperCase())}
            />
          </label>
          {error && <ErrorSummary title="Não foi possível excluir" message={error} />}
        </div>
      </ConfirmDialog>
    </div>
  );
}
