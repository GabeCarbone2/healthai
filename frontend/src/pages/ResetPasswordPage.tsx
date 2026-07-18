import { Activity, CheckCircle2, Eye, EyeOff, KeyRound } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import { resetPassword } from "../api";
import { ErrorSummary } from "../components/ErrorSummary";
import { HealthAiLogo } from "../components/HealthAiLogo";
import { PageFooter } from "../components/PageFooter";
import type { PrivacyInfo } from "../types";

type Props = { token: string; privacy: PrivacyInfo };

export function ResetPasswordPage({ token, privacy }: Props) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (token) window.history.replaceState({}, "", "/reset-password");
  }, [token]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirmation) {
      setError("As senhas não coincidem.");
      window.setTimeout(() => errorRef.current?.focus(), 0);
      return;
    }
    setLoading(true);
    setError("");
    try {
      await resetPassword(token, password);
      setComplete(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível redefinir a senha.");
      window.setTimeout(() => errorRef.current?.focus(), 0);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="credential-page">
      <section className="credential-card">
        <a className="credential-brand" href="/">
          <HealthAiLogo className="healthai-logo" />
          <strong>HealthAI</strong>
        </a>
        {complete ? (
          <div className="credential-success">
            <CheckCircle2 size={32} />
            <span className="page-eyebrow">Senha atualizada</span>
            <h1>Redefinição concluída</h1>
            <p>As sessões anteriores foram encerradas. Entre novamente com a nova senha.</p>
            <a className="primary-button" href="/">Entrar no HealthAI</a>
          </div>
        ) : (
          <>
            <span className="credential-icon"><KeyRound size={24} /></span>
            <span className="page-eyebrow">Link de uso único</span>
            <h1>Definir nova senha</h1>
            <p>Use no mínimo 8 caracteres. Ao concluir, todas as sessões anteriores serão encerradas.</p>
            {!token && <ErrorSummary ref={errorRef} message="O link de recuperação está incompleto." />}
            {error && <ErrorSummary ref={errorRef} message={error} />}
            <form onSubmit={submit}>
              <label htmlFor="new-password">
                <span>Nova senha</span>
                <div className="password-input">
                  <input id="new-password" type={showPassword ? "text" : "password"} autoComplete="new-password" minLength={8} maxLength={128} required value={password} onChange={(event) => setPassword(event.target.value)} />
                  <button type="button" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}>
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </label>
              <label htmlFor="new-password-confirmation">
                <span>Confirmar nova senha</span>
                <input id="new-password-confirmation" type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
              </label>
              <button type="submit" className="primary-button" disabled={!token || loading}>
                {loading ? <Activity size={17} className="spin" /> : <KeyRound size={17} />}
                {loading ? "Redefinindo..." : "Redefinir senha"}
              </button>
            </form>
          </>
        )}
      </section>
      <PageFooter contact={privacy.contact} variant="public" />
    </main>
  );
}
