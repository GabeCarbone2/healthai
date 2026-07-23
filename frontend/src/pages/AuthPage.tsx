import {
  Activity,
  AlertCircle,
  ArrowRight,
  BrainCircuit,
  Eye,
  EyeOff,
  LockKeyhole,
  LogIn,
  MailCheck,
  Send,
  ShieldCheck,
  UserPlus,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";

import { login, register, resendVerification } from "../api";
import { ErrorSummary } from "../components/ErrorSummary";
import { HealthAiLogo } from "../components/HealthAiLogo";
import { PageFooter } from "../components/PageFooter";
import { PrivacyNotice } from "../components/PrivacyNotice";
import type { PrivacyInfo, User } from "../types";

type Props = {
  onAuthenticated: (user: User) => void;
  privacy: PrivacyInfo;
};

const BRAZILIAN_STATES = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
  "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
  "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

export function AuthPage({ onAuthenticated, privacy }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [crm, setCrm] = useState("");
  const [crmUf, setCrmUf] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [verificationEmailSent, setVerificationEmailSent] = useState(true);
  const [resending, setResending] = useState(false);
  const [resendNotice, setResendNotice] = useState("");
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [confirmationTouched, setConfirmationTouched] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  function changeMode(nextMode: "login" | "register") {
    setMode(nextMode);
    setError("");
    setPassword("");
    setPasswordConfirmation("");
    setPrivacyAccepted(false);
    setTermsAccepted(false);
    setPrivacyOpen(false);
    setPasswordTouched(false);
    setConfirmationTouched(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submittingRef.current || loading) return;
    if (mode === "register" && password !== passwordConfirmation) {
      setConfirmationTouched(true);
      setError("As senhas não coincidem.");
      return;
    }
    submittingRef.current = true;
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        onAuthenticated(await login(email, password));
      } else {
        const registration = await register(
          name,
          crm,
          crmUf,
          email,
          password,
          privacyAccepted,
          termsAccepted,
        );
        setVerificationEmail(registration.email);
        setVerificationEmailSent(registration.email_sent);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível autenticar.",
      );
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  }

  async function resend() {
    setResending(true);
    setResendNotice("");
    try {
      await resendVerification(verificationEmail);
      setResendNotice(
        "Se a conta estiver aguardando confirmação, um novo link será enviado.",
      );
    } catch (requestError) {
      setResendNotice(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível solicitar outro e-mail.",
      );
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="auth-page">
      <a className="skip-link" href="#acesso">
        Ir para o acesso
      </a>
      <div className="auth-scroll-meter" aria-hidden="true">
        <span>ROLAGEM</span>
        <i><b /></i>
      </div>

      <header className="auth-topbar">
        <div className="auth-topbar-inner">
          <a className="auth-brand" href="#inicio" aria-label="HealthAI — início">
            <span>
              <HealthAiLogo className="healthai-logo" title="HealthAI" />
            </span>
            <div>
              <strong>HealthAI</strong>
              <small>Clinical intelligence</small>
            </div>
          </a>
          <nav className="auth-navigation" aria-label="Navegação pública">
            <a href="#inicio">Início</a>
            <a href="#recursos">Recursos</a>
            <a href="#acesso">Acesso</a>
          </nav>
          <div className="auth-security-note">
            <ShieldCheck size={15} aria-hidden="true" />
            Acesso restrito a médicos
          </div>
        </div>
      </header>

      <main className="auth-main">
        <section className="auth-hero" id="inicio" aria-labelledby="auth-hero-title">
          <div className="auth-hero-inner">
          <aside className="auth-intro" data-reveal="left">
            <div className="auth-eyebrow">
              <Activity size={15} aria-hidden="true" />
              HealthAI / triagem acadêmica
            </div>
            <h1 id="auth-hero-title">
              Probabilidade sem contexto <em>é só ruído.</em>
            </h1>
            <p className="auth-description">
              O HealthAI organiza sinais clínicos, explicita o limiar e mostra
              o que o modelo não sabe — para apoiar triagens sem simular um
              diagnóstico.
            </p>
            <div className="auth-hero-actions">
              <a
                className="auth-hero-primary"
                href="#acesso"
                onClick={() => changeMode("login")}
              >
                Entrar no HealthAI
                <ArrowRight size={18} aria-hidden="true" />
              </a>
              <a
                className="auth-hero-secondary"
                href="#acesso"
                onClick={() => changeMode("register")}
              >
                Criar conta profissional
              </a>
            </div>
            <p className="auth-trust-line">
              <ShieldCheck size={16} aria-hidden="true" />
              Uso acadêmico, acesso profissional e dados pseudonimizados
            </p>
          </aside>

          <div className="auth-signal-stage" aria-hidden="true" data-reveal="right">
            <div className="auth-signal-index">
              <span>LEITURA / APOIO</span>
              <b>NÃO DIAGNÓSTICO</b>
            </div>
            <svg className="auth-signal-plot" viewBox="0 0 620 360">
              <g className="signal-grid">
                <path d="M20 60H600M20 120H600M20 180H600M20 240H600M20 300H600" />
                <path d="M80 20V340M160 20V340M240 20V340M320 20V340M400 20V340M480 20V340M560 20V340" />
              </g>
              <path className="signal-base" d="M20 214H600" />
              <path
                className="signal-trace"
                d="M20 214H116L142 197L169 214H232L258 211L278 130L307 286L338 174L363 214H426L449 202L476 214H600"
              />
              <circle className="signal-node node-a" cx="278" cy="130" r="7" />
              <circle className="signal-node node-b" cx="338" cy="174" r="7" />
            </svg>
            <div className="auth-signal-legend">
              <span><i /> probabilidade</span>
              <span><i /> limiar</span>
              <span><i /> completude</span>
            </div>
            <HealthAiLogo className="auth-signal-mark" />
          </div>
          </div>
        </section>

        <section className="auth-feature-section" id="recursos" aria-labelledby="auth-features-title">
          <header className="auth-section-heading" data-reveal="up">
            <span>O que chega com o número</span>
            <h2 id="auth-features-title">A estimativa vem acompanhada de evidências.</h2>
            <p>
              Cada resultado expõe origem, limite e completude. O essencial
              aparece primeiro; a parte técnica continua disponível.
            </p>
          </header>
          <div className="auth-feature-grid">
            <article data-reveal="left">
              <span><BrainCircuit size={24} aria-hidden="true" /></span>
              <small>01 / Contexto do modelo</small>
              <h3>Pima e NHANES não se misturam</h3>
              <p>Cada perfil mantém população, variáveis e limitações próprias — sem transformar bases diferentes em uma falsa certeza.</p>
            </article>
            <article data-reveal="right">
              <span><ShieldCheck size={24} aria-hidden="true" /></span>
              <small>02 / Dados mínimos</small>
              <h3>O formulário termina na inferência</h3>
              <p>Os valores clínicos usados no cálculo não entram no histórico; o identificador permanece pseudonimizado.</p>
            </article>
            <article data-reveal="right">
              <span><LockKeyhole size={24} aria-hidden="true" /></span>
              <small>03 / Leitura do resultado</small>
              <h3>Limiar à vista, incerteza também</h3>
              <p>Probabilidade, completude, versão e explicações acompanham a classe prevista em cada avaliação.</p>
            </article>
          </div>
        </section>

        <section className="auth-access-section" id="acesso" aria-labelledby="auth-access-title">
          <div className="auth-access-copy" data-reveal="left">
            <span className="auth-eyebrow">
              <LockKeyhole size={15} aria-hidden="true" />
              Entrada controlada
            </span>
            <h2 id="auth-access-title">O acesso clínico começa pela verificação.</h2>
            <p>
              Entre com sua conta ou solicite um novo acesso profissional. A
              liberação das avaliações depende da verificação do CRM.
            </p>
            <ul>
              <li><ShieldCheck size={17} aria-hidden="true" /> Conta individual e sessão protegida</li>
              <li><ShieldCheck size={17} aria-hidden="true" /> Verificação profissional antes do uso clínico</li>
              <li><ShieldCheck size={17} aria-hidden="true" /> Consentimento e limites apresentados com clareza</li>
            </ul>
          </div>

          <div className="auth-access" data-reveal="right">
          <section className={`auth-panel ${mode}`}>
          <div className="auth-panel-shine" aria-hidden="true" />
          {verificationEmail ? (
            <div className="verification-sent">
              <span className="verification-sent-icon">
                <MailCheck size={34} />
              </span>
              <small>Conta criada</small>
              <h2>Verifique seu e-mail</h2>
              <p>
                {verificationEmailSent ? (
                  <>
                    Enviamos um link de confirmação para{" "}
                    <strong>{verificationEmail}</strong>. Ele expira em 24
                    horas.
                  </>
                ) : (
                  <>
                    Sua conta foi criada, mas o primeiro envio falhou. Solicite
                    um novo link para <strong>{verificationEmail}</strong>.
                  </>
                )}
              </p>
              {resendNotice && (
                <div className="verification-notice" role="status">
                  {resendNotice}
                </div>
              )}
              <button
                type="button"
                className="auth-submit"
                disabled={resending}
                onClick={resend}
              >
                {resending ? <Activity size={18} /> : <Send size={18} />}
                {resending ? "Solicitando..." : "Reenviar e-mail"}
              </button>
              <button
                type="button"
                className="auth-text-button"
                onClick={() => {
                  setVerificationEmail("");
                  setVerificationEmailSent(true);
                  changeMode("login");
                }}
              >
                Voltar para entrar
              </button>
            </div>
          ) : (
            <>
          <header className="auth-panel-header">
            <span className="auth-panel-icon">
              <HealthAiLogo className="healthai-logo" title="HealthAI" />
            </span>
            <div>
              <small>{mode === "login" ? "Bem-vindo de volta" : "Novo acesso"}</small>
              <h2>{mode === "login" ? "Entre na sua conta" : "Crie sua conta"}</h2>
            </div>
          </header>

          <div className="auth-switch" aria-label="Modo de autenticação">
            <button
              type="button"
              className={mode === "login" ? "active" : ""}
              onClick={() => changeMode("login")}
            >
              Entrar
            </button>
            <button
              type="button"
              className={mode === "register" ? "active" : ""}
              onClick={() => changeMode("register")}
            >
              Criar conta
            </button>
          </div>

          <form onSubmit={submit} className="auth-form">
            {error && mode === "register" && (
              <ErrorSummary
                ref={errorRef}
                title="Não foi possível continuar"
                message={error}
              />
            )}

            {mode === "register" ? (
              <fieldset className="auth-fieldset">
                <legend>Dados profissionais</legend>
                <label htmlFor="register-name">
                  <span>Nome</span>
                  <input id="register-name" type="text" autoComplete="name" minLength={2} maxLength={120} placeholder="Como devemos chamar você?" required value={name} onChange={(event) => setName(event.target.value)} />
                </label>
                <div className="professional-fields">
                  <label htmlFor="register-crm">
                    <span>CRM</span>
                    <input id="register-crm" type="text" inputMode="numeric" minLength={1} maxLength={10} pattern="[0-9]{1,10}" placeholder="Somente números" required value={crm} onChange={(event) => setCrm(event.target.value.replace(/\D/g, ""))} />
                  </label>
                  <label htmlFor="register-crm-uf">
                    <span>UF do CRM</span>
                    <select id="register-crm-uf" required value={crmUf} onChange={(event) => setCrmUf(event.target.value)}>
                      <option value="" disabled>Selecione</option>
                      {BRAZILIAN_STATES.map((state) => <option key={state} value={state}>{state}</option>)}
                    </select>
                  </label>
                </div>
                <label htmlFor="register-email">
                  <span>E-mail</span>
                  <input id="register-email" type="email" autoComplete="email" placeholder="voce@exemplo.com" required value={email} onChange={(event) => { setEmail(event.target.value); setError(""); }} />
                </label>
                <small className="fieldset-note">O CRM passa por análise manual antes da liberação das avaliações.</small>
              </fieldset>
            ) : (
              <label htmlFor="login-email">
                <span>E-mail</span>
                <input id="login-email" type="email" autoComplete="email" placeholder="voce@exemplo.com" required value={email} aria-invalid={Boolean(error)} aria-describedby={error ? "login-field-error" : undefined} onChange={(event) => { setEmail(event.target.value); setError(""); }} />
              </label>
            )}

            <fieldset className={mode === "register" ? "auth-fieldset" : "auth-fieldset login-security"}>
              {mode === "register" && <legend>Segurança</legend>}
              <label htmlFor="auth-password">
                <span>Senha</span>
                <div className="password-input">
                  <input
                    id="auth-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete={mode === "login" ? "current-password" : "new-password"}
                    minLength={8}
                    maxLength={128}
                    placeholder="Digite sua senha"
                    required
                    value={password}
                    aria-invalid={mode === "login" && Boolean(error)}
                    aria-describedby={mode === "register" ? "password-rules" : error ? "login-field-error" : undefined}
                    onBlur={() => setPasswordTouched(true)}
                    onKeyUp={(event) => setCapsLock(event.getModifierState("CapsLock"))}
                    onChange={(event) => { setPassword(event.target.value); setError(""); }}
                  />
                  <button type="button" onClick={() => setShowPassword((current) => !current)} title={showPassword ? "Ocultar senha" : "Mostrar senha"} aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}>
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {capsLock && <small className="caps-lock-warning">Caps Lock está ativado.</small>}
              </label>

              {mode === "register" && (
                <>
                  <ul className="password-rules" id="password-rules">
                    <li className={password.length >= 8 ? "met" : passwordTouched ? "unmet" : ""}>Mínimo de 8 caracteres</li>
                    <li className={password && password === passwordConfirmation ? "met" : confirmationTouched ? "unmet" : ""}>As duas senhas devem coincidir</li>
                  </ul>
                  <label htmlFor="password-confirmation">
                    <span>Confirmar senha</span>
                    <input id="password-confirmation" type="password" autoComplete="new-password" minLength={8} maxLength={128} placeholder="Repita sua senha" required value={passwordConfirmation} aria-invalid={confirmationTouched && password !== passwordConfirmation} onBlur={() => setConfirmationTouched(true)} onKeyUp={(event) => setCapsLock(event.getModifierState("CapsLock"))} onChange={(event) => { setPasswordConfirmation(event.target.value); setError(""); }} />
                  </label>
                </>
              )}
            </fieldset>

            {mode === "login" && error && (
              <div
                className="auth-field-error"
                id="login-field-error"
                ref={errorRef}
                role="alert"
                tabIndex={-1}
              >
                <AlertCircle size={16} aria-hidden="true" />
                <span>{error}</span>
              </div>
            )}

            {mode === "register" && (
              <fieldset className="auth-fieldset privacy-fieldset">
                <legend>Privacidade</legend>
                <details className="registration-privacy" open={privacyOpen} onToggle={(event) => setPrivacyOpen(event.currentTarget.open)}>
                  <summary aria-expanded={privacyOpen}>Ler aviso de privacidade</summary>
                  <PrivacyNotice info={privacy} />
                </details>
                <label className="consent-check">
                  <input type="checkbox" required checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} />
                  <span>Li o aviso e consinto com o tratamento descrito.</span>
                </label>
                <label className="consent-check">
                  <input type="checkbox" required checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} />
                  <span>Li e aceito os <a href="/terms" target="_blank" rel="noreferrer">Termos de Uso</a>.</span>
                </label>
              </fieldset>
            )}

            {mode === "login" && (
              <a className="forgot-password-link" href="/forgot-password">
                Esqueci minha senha
              </a>
            )}

            <p className="auth-medical-note">
              <ShieldCheck size={16} aria-hidden="true" />
              O HealthAI é uma ferramenta acadêmica de apoio à triagem e não
              substitui diagnóstico ou avaliação médica.
            </p>

            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? (
                <Activity size={18} />
              ) : mode === "login" ? (
                <LogIn size={18} />
              ) : (
                <UserPlus size={18} />
              )}
              {loading
                ? "Aguarde..."
                : mode === "login"
                  ? "Entrar no HealthAI"
                  : "Criar minha conta"}
            </button>
          </form>

          <footer className="auth-panel-footer">
            <LockKeyhole size={13} />
            Sessão protegida e dados clínicos não persistidos
          </footer>
            </>
          )}
          </section>

          </div>
        </section>
      </main>
      <PageFooter contact={privacy.contact} variant="public" />
    </div>
  );
}
