import { Activity, ArrowLeft, Mail, Send } from "lucide-react";
import { FormEvent, useRef, useState } from "react";

import { requestPasswordReset } from "../api";
import { ErrorSummary } from "../components/ErrorSummary";
import { HealthAiLogo } from "../components/HealthAiLogo";
import { PageFooter } from "../components/PageFooter";
import type { PrivacyInfo } from "../types";

type Props = { privacy: PrivacyInfo };

export function ForgotPasswordPage({ privacy }: Props) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível solicitar a recuperação.");
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
        {sent ? (
          <div className="credential-success">
            <Mail size={30} />
            <span className="page-eyebrow">Solicitação recebida</span>
            <h1>Confira seu e-mail</h1>
            <p>
              Se existir uma conta ativa para <strong>{email}</strong>, enviaremos
              um link válido por uma hora. A resposta é sempre a mesma para proteger contas cadastradas.
            </p>
            <a className="primary-button" href="/">Voltar para entrar</a>
          </div>
        ) : (
          <>
            <span className="credential-icon"><Mail size={24} /></span>
            <span className="page-eyebrow">Acesso à conta</span>
            <h1>Recuperar senha</h1>
            <p>Informe seu e-mail para receber um link de redefinição de uso único.</p>
            {error && <ErrorSummary ref={errorRef} message={error} />}
            <form onSubmit={submit}>
              <label htmlFor="recovery-email">
                <span>E-mail</span>
                <input id="recovery-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
              </label>
              <button type="submit" className="primary-button" disabled={loading}>
                {loading ? <Activity size={17} className="spin" /> : <Send size={17} />}
                {loading ? "Enviando..." : "Enviar link de recuperação"}
              </button>
            </form>
            <a className="credential-back" href="/"><ArrowLeft size={15} /> Voltar para entrar</a>
          </>
        )}
      </section>
      <PageFooter contact={privacy.contact} variant="public" />
    </main>
  );
}
