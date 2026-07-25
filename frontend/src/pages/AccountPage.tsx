import {
  Activity,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  Eye,
  EyeOff,
  FileSignature,
  FileUp,
  ShieldCheck,
  Trash2,
  UserRound,
  XCircle,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  createCrmVerificationChallenge,
  deleteAccount,
  downloadCrmVerificationChallenge,
  fetchCrmVerification,
  submitCrm,
  submitSignedCrmVerification,
} from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorSummary } from "../components/ErrorSummary";
import { PrivacyNotice } from "../components/PrivacyNotice";
import type {
  CrmVerificationChallenge,
  PrivacyInfo,
  User,
} from "../types";
import {
  formatBrazilianDate,
  formatBrazilianDateTime,
} from "../utils/date";

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
  const [challenge, setChallenge] =
    useState<CrmVerificationChallenge | null>(null);
  const [challengeLoading, setChallengeLoading] = useState(false);
  const [signedPdf, setSignedPdf] = useState<File | null>(null);
  const [verificationLoading, setVerificationLoading] = useState(false);
  const [verificationError, setVerificationError] = useState("");
  const [verificationNotice, setVerificationNotice] = useState("");

  useEffect(() => {
    if (
      user.crm_status === "approved"
      || !user.crm
      || !user.crm_uf
    ) {
      setChallenge(null);
      return;
    }
    let active = true;
    fetchCrmVerification()
      .then((status) => {
        if (active) setChallenge(status.active_challenge);
      })
      .catch((requestError) => {
        if (active) {
          setVerificationError(
            requestError instanceof Error
              ? requestError.message
              : "Não foi possível consultar a verificação.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [user.crm, user.crm_status, user.crm_uf]);

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
      const updatedUser = await submitCrm(crm, crmUf);
      setChallenge(null);
      setSignedPdf(null);
      onUserUpdated(updatedUser);
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

  async function createAndDownloadChallenge() {
    setChallengeLoading(true);
    setVerificationError("");
    setVerificationNotice("");
    try {
      const createdChallenge = await createCrmVerificationChallenge();
      setChallenge(createdChallenge);
      setSignedPdf(null);
      await downloadCrmVerificationChallenge(createdChallenge);
      setVerificationNotice(
        "Documento gerado. Assine o PDF e envie o arquivo resultante abaixo.",
      );
    } catch (requestError) {
      setVerificationError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível gerar o documento de verificação.",
      );
    } finally {
      setChallengeLoading(false);
    }
  }

  async function downloadActiveChallenge() {
    if (!challenge) return;
    setChallengeLoading(true);
    setVerificationError("");
    try {
      await downloadCrmVerificationChallenge(challenge);
    } catch (requestError) {
      setVerificationError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível baixar o documento.",
      );
    } finally {
      setChallengeLoading(false);
    }
  }

  async function verifySignedPdf(event: FormEvent) {
    event.preventDefault();
    if (!challenge || !signedPdf) return;
    setVerificationLoading(true);
    setVerificationError("");
    setVerificationNotice("");
    try {
      const updatedUser = await submitSignedCrmVerification(
        challenge.id,
        signedPdf,
      );
      setChallenge(null);
      setSignedPdf(null);
      onUserUpdated(updatedUser);
    } catch (requestError) {
      setVerificationError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível validar o PDF assinado.",
      );
    } finally {
      setVerificationLoading(false);
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
            <button
              type="button"
              className="show-data-button"
              aria-pressed={showData}
              title={showData ? "Ocultar dados pessoais" : "Mostrar dados pessoais"}
              onClick={() => setShowData((current) => !current)}
            >
              {showData
                ? <EyeOff size={16} aria-hidden="true" />
                : <Eye size={16} aria-hidden="true" />}
              {showData ? "Ocultar dados" : "Mostrar dados"}
            </button>
          </header>
          <dl className="account-data-list">
            <div><dt>Nome</dt><dd>{showData ? user.name : `${user.name.slice(0, 1)}••••••`}</dd></div>
            <div><dt>E-mail</dt><dd>{showData ? user.email : maskEmail(user.email)}</dd></div>
            <div><dt>CRM</dt><dd>{user.crm && user.crm_uf ? `${showData ? user.crm : maskCrm(user.crm)}/${user.crm_uf}` : "Não informado"}</dd></div>
            <div><dt>Conta criada em</dt><dd>{formatBrazilianDate(user.created_at, "long")}</dd></div>
            <div><dt>Aviso de privacidade aceito</dt><dd>{user.privacy_accepted_at ? `${formatBrazilianDate(user.privacy_accepted_at, "long")} · versão ${user.privacy_notice_version}` : "Pendente"}</dd></div>
            <div><dt>Termos aceitos</dt><dd>{user.terms_accepted_at ? `${formatBrazilianDate(user.terms_accepted_at, "long")} · versão ${user.terms_version}` : "Pendente"}</dd></div>
          </dl>
        </section>

        <section className="account-card storage-card">
          <header>
            <Database size={22} aria-hidden="true" />
            <div>
              <h2>Dados das avaliações</h2>
              <p>Prazo de retenção: até {privacy.result_retention_days} dias.</p>
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
          <span className="status-kicker">Verificação por certificado digital</span>
          <h2>Cadastro profissional</h2>
          <span className={`status-badge ${user.crm_status ?? "missing"}`}>
            {user.crm_status === "approved" ? (
              <><CheckCircle2 size={15} aria-hidden="true" /> Cadastro aprovado</>
            ) : user.crm_status === "rejected" ? (
              <><XCircle size={15} aria-hidden="true" /> Cadastro não aprovado</>
            ) : (
              <><Clock3 size={15} aria-hidden="true" /> Aguardando análise</>
            )}
          </span>
          <p>
            {user.crm_status === "approved"
              ? `Cadastro aprovado em ${formatBrazilianDate(user.crm_verified_at)} por validação criptográfica do certificado profissional.`
              : user.crm_status === "rejected"
                ? user.crm_rejection_reason ?? "Revise os dados informados e envie novamente."
                : user.crm
                  ? "Comprove o CRM assinando um PDF de uso único com seu Certificado Digital do CFM."
                  : "Informe CRM e UF para iniciar a verificação profissional."}
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
                {crmLoading ? "Salvando..." : "Salvar CRM"}
              </button>
            </form>
          )}
          {crmError && <ErrorSummary title="Não foi possível enviar" message={crmError} />}
          {user.crm_status !== "approved" && user.crm && user.crm_uf && (
            <div className="crm-verification-flow">
              <ol>
                <li>
                  <span>1</span>
                  <div>
                    <strong>Baixe o documento de uso único</strong>
                    <p>Ele vincula esta conta ao CRM informado e expira em poucos minutos.</p>
                  </div>
                </li>
                <li>
                  <span>2</span>
                  <div>
                    <strong>Assine com seu certificado profissional</strong>
                    <p>Use um assinador PAdES com o Certificado Digital do CFM vinculado ao mesmo CRM e UF.</p>
                  </div>
                </li>
                <li>
                  <span>3</span>
                  <div>
                    <strong>Envie o PDF assinado</strong>
                    <p>A aprovação ocorre automaticamente após a validação da assinatura e do certificado.</p>
                  </div>
                </li>
              </ol>

              <div className="crm-challenge-actions">
                <button
                  type="button"
                  onClick={createAndDownloadChallenge}
                  disabled={challengeLoading || verificationLoading}
                >
                  {challengeLoading
                    ? <Activity size={16} />
                    : <FileSignature size={16} />}
                  {challenge
                    ? "Gerar novo documento"
                    : "Gerar e baixar PDF"}
                </button>
                {challenge && (
                  <button
                    type="button"
                    className="secondary"
                    onClick={downloadActiveChallenge}
                    disabled={challengeLoading || verificationLoading}
                  >
                    <Download size={16} />
                    Baixar novamente
                  </button>
                )}
              </div>

              {challenge && (
                <form
                  className="signed-pdf-form"
                  onSubmit={verifySignedPdf}
                  noValidate
                >
                  <label htmlFor="signed-crm-pdf">
                    <span>PDF assinado</span>
                    <input
                      id="signed-crm-pdf"
                      type="file"
                      accept=".pdf,application/pdf"
                      required
                      onChange={(event) => {
                        setSignedPdf(event.target.files?.[0] ?? null);
                        setVerificationError("");
                      }}
                    />
                    <small>
                      Desafio válido até{" "}
                      {formatBrazilianDateTime(challenge.expires_at)}. O PDF
                      enviado não é armazenado.
                    </small>
                  </label>
                  <button
                    type="submit"
                    disabled={!signedPdf || verificationLoading}
                  >
                    {verificationLoading
                      ? <Activity size={16} />
                      : <FileUp size={16} />}
                    {verificationLoading
                      ? "Validando assinatura..."
                      : "Validar PDF assinado"}
                  </button>
                </form>
              )}
              {verificationNotice && (
                <p className="crm-verification-notice" role="status">
                  <CheckCircle2 size={16} />
                  {verificationNotice}
                </p>
              )}
              {verificationError && (
                <ErrorSummary
                  title="Não foi possível verificar"
                  message={verificationError}
                />
              )}
            </div>
          )}
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
          <p>Esta ação removerá permanentemente sua conta, sessões e resultados associados. Não poderá ser desfeita.</p>
        </div>
        <button type="button" onClick={() => setConfirming(true)}>
          <Trash2 size={16} />
          Excluir minha conta
        </button>
      </section>

      <ConfirmDialog
        open={confirming}
        title="Excluir conta permanentemente?"
        description="Esta ação removerá permanentemente sua conta, sessões e resultados associados. Não poderá ser desfeita."
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
