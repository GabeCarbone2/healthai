import {
  Activity,
  AlertCircle,
  ArrowRight,
  BrainCircuit,
  Database,
  Eye,
  EyeOff,
  Fingerprint,
  Gauge,
  ListChecks,
  LockKeyhole,
  LogIn,
  MailCheck,
  Menu,
  Send,
  ShieldCheck,
  UserPlus,
  X,
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

const PUBLIC_SECTIONS = [
  { id: "inicio", label: "Início" },
  { id: "como-funciona", label: "Como funciona" },
  { id: "seguranca", label: "Segurança e privacidade" },
  { id: "limitacoes", label: "Limitações" },
  { id: "acesso", label: "Acesso" },
] as const;

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
  const [activeSection, setActiveSection] = useState("inicio");
  const [menuOpen, setMenuOpen] = useState(false);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  useEffect(() => {
    if (typeof window.IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntry = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
        if (visibleEntry?.target.id) setActiveSection(visibleEntry.target.id);
      },
      {
        rootMargin: "-28% 0px -58% 0px",
        threshold: [0, 0.25, 0.6],
      },
    );

    PUBLIC_SECTIONS.forEach(({ id }) => {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    });

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!menuOpen) return;

    function closeMenu(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }

    document.addEventListener("keydown", closeMenu);
    return () => document.removeEventListener("keydown", closeMenu);
  }, [menuOpen]);

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

  function followSection(section: string, nextMode?: "login" | "register") {
    if (nextMode) changeMode(nextMode);
    setActiveSection(section);
    setMenuOpen(false);
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
          <a
            className="auth-brand"
            href="#inicio"
            aria-label="HealthAI — início"
            onClick={() => followSection("inicio")}
          >
            <span>
              <HealthAiLogo className="healthai-logo" title="HealthAI" />
            </span>
            <div>
              <strong>HealthAI</strong>
              <small>Apoio à triagem</small>
            </div>
          </a>

          <button
            type="button"
            className="auth-menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="auth-public-navigation"
            aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
            onClick={() => setMenuOpen((current) => !current)}
          >
            {menuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>

          <nav
            className={`auth-navigation ${menuOpen ? "open" : ""}`}
            id="auth-public-navigation"
            aria-label="Navegação pública"
          >
            {PUBLIC_SECTIONS.map(({ id, label }) => (
              <a
                href={`#${id}`}
                className={activeSection === id ? "active" : ""}
                aria-current={activeSection === id ? "location" : undefined}
                onClick={() => followSection(id)}
                key={id}
              >
                {label}
              </a>
            ))}
          </nav>

          <a
            className="auth-header-cta"
            href="#acesso"
            onClick={() => followSection("acesso", "login")}
          >
            Entrar
          </a>
        </div>
      </header>

      <main className="auth-main">
        <section className="auth-hero" id="inicio" aria-labelledby="auth-hero-title">
          <div className="auth-hero-inner">
          <aside className="auth-intro" data-reveal="left">
            <div className="auth-eyebrow">
              <Activity size={15} aria-hidden="true" />
              APOIO À TRIAGEM DE RISCO DE DIABETES
            </div>
            <h1 id="auth-hero-title">Apoio à triagem de risco de diabetes</h1>
            <p className="auth-description">
              Organize dados clínicos, consulte a estimativa de risco e interprete
              o resultado com informações sobre completude e limitações.
            </p>
            <p className="auth-concept-line">
              Probabilidade sem contexto <em>é só ruído.</em>
            </p>
            <div className="auth-hero-actions">
              <a
                className="auth-hero-primary"
                href="#acesso"
                onClick={() => followSection("acesso", "login")}
              >
                Iniciar avaliação
                <ArrowRight size={18} aria-hidden="true" />
              </a>
              <a
                className="auth-hero-secondary"
                href="#acesso"
                onClick={() => followSection("acesso", "login")}
              >
                Entrar na plataforma
              </a>
            </div>
            <p className="auth-trust-line">
              <ShieldCheck size={16} aria-hidden="true" />
              O HealthAI não substitui diagnóstico, exames, avaliação médica ou
              julgamento clínico.
            </p>
          </aside>

          <div className="auth-signal-stage" data-reveal="right" aria-hidden="true">
            <div className="auth-signal-index">
              <span>Diabetes em foco</span>
              <b>Ilustração educacional</b>
            </div>
            <div className="auth-diabetes-visual">
              <div className="auth-diabetes-frame">
                <img
                  src="/diabetes-glucose-monitor.svg"
                  alt=""
                  width="640"
                  height="480"
                />
              </div>
              <div className="auth-diabetes-tags">
                <span><i /> Glicose no sangue</span>
                <span><i /> Acompanhamento metabólico</span>
              </div>
            </div>
            <div className="auth-signal-legend">
              <span>Glicosímetro e tira reagente</span>
              <span>Não representa resultado de paciente</span>
            </div>
          </div>
          </div>
        </section>

        <section className="auth-feature-section" id="como-funciona" aria-labelledby="auth-features-title">
          <header className="auth-section-heading" data-reveal="left">
            <span>Como funciona</span>
            <h2 id="auth-features-title">Da informação disponível à leitura contextualizada.</h2>
            <p>
              Um fluxo objetivo organiza a avaliação sem substituir o raciocínio
              ou a decisão médica.
            </p>
          </header>
          <ol className="auth-workflow-grid">
            <li data-reveal="up">
              <small>01</small>
              <h3>Informe os dados clínicos disponíveis</h3>
              <p>Registre as informações compatíveis com o perfil da avaliação.</p>
            </li>
            <li data-reveal="up">
              <small>02</small>
              <h3>Revise a completude das informações</h3>
              <p>Confira campos informados, ausentes e passíveis de estimativa.</p>
            </li>
            <li data-reveal="up">
              <small>03</small>
              <h3>Calcule a estimativa de risco</h3>
              <p>Consulte a classificação da triagem e a probabilidade estimada.</p>
            </li>
            <li data-reveal="up">
              <small>04</small>
              <h3>Interprete no contexto médico</h3>
              <p>Considere histórico, exames, condições e julgamento clínico.</p>
            </li>
          </ol>
        </section>

        <section className="auth-benefits-section" aria-labelledby="auth-benefits-title">
          <header className="auth-section-heading" data-reveal="left">
            <span>Apoio ao fluxo médico</span>
            <h2 id="auth-benefits-title">Informação organizada para uma triagem mais objetiva.</h2>
            <p>
              A avaliação reúne o essencial para registrar, interpretar e
              acompanhar uma estimativa de risco.
            </p>
          </header>
          <div className="auth-feature-grid auth-benefit-grid">
            <article data-reveal="up">
              <span><ListChecks size={24} aria-hidden="true" /></span>
              <small>01 / Avaliação estruturada</small>
              <h3>Dados clínicos estruturados</h3>
              <p>Organize os principais fatores clínicos em um único fluxo de avaliação.</p>
            </article>
            <article data-reveal="up">
              <span><Gauge size={24} aria-hidden="true" /></span>
              <small>02 / Interpretação objetiva</small>
              <h3>Estimativa com contexto</h3>
              <p>Consulte a estimativa de risco, a completude dos dados e as limitações do resultado.</p>
            </article>
            <article data-reveal="up">
              <span><LockKeyhole size={24} aria-hidden="true" /></span>
              <small>03 / Privacidade</small>
              <h3>O formulário termina no cálculo</h3>
              <p>Os valores clínicos utilizados no cálculo não são armazenados no histórico.</p>
            </article>
            <article data-reveal="up">
              <span><Fingerprint size={24} aria-hidden="true" /></span>
              <small>04 / Rastreabilidade</small>
              <h3>Avaliações identificáveis</h3>
              <p>Cada avaliação registra data, perfil utilizado, resultado e versão da análise.</p>
            </article>
          </div>
        </section>

        <section className="auth-privacy-section" id="seguranca" aria-labelledby="auth-privacy-title">
          <header className="auth-section-heading" data-reveal="left">
            <span>Segurança e privacidade</span>
            <h2 id="auth-privacy-title">O mínimo necessário, com rastreabilidade.</h2>
            <p>
              O histórico mantém o resultado e seus metadados de leitura, sem
              conservar os valores clínicos utilizados no cálculo.
            </p>
          </header>
          <ol className="auth-privacy-list">
            <li data-reveal="up">
              <span><Database size={22} aria-hidden="true" /></span>
              <div>
                <small>01</small>
                <h3>Dados clínicos somente no cálculo</h3>
                <p>Os valores informados são utilizados somente no cálculo e não são persistidos no histórico.</p>
              </div>
            </li>
            <li data-reveal="up">
              <span><Fingerprint size={22} aria-hidden="true" /></span>
              <div>
                <small>02</small>
                <h3>Identificador pseudonimizado</h3>
                <p>O histórico é associado a um código <code>PAC-…</code>. Pseudonimização não é anonimização.</p>
              </div>
            </li>
            <li data-reveal="up">
              <span><ListChecks size={22} aria-hidden="true" /></span>
              <div>
                <small>03</small>
                <h3>Resultado rastreável</h3>
                <p>Resultado, data, perfil e versão da análise acompanham cada registro.</p>
              </div>
            </li>
          </ol>
        </section>

        <section className="auth-limitations-section" id="limitacoes" aria-labelledby="auth-limitations-title">
          <header className="auth-section-heading" data-reveal="left">
            <span>Limitações</span>
            <h2 id="auth-limitations-title">Uma estimativa precisa ser lida dentro do seu contexto.</h2>
            <p>
              O resultado depende das informações disponíveis, do perfil
              selecionado e das limitações metodológicas da análise.
            </p>
          </header>
          <div className="auth-limitations-grid">
            <article data-reveal="up">
              <AlertCircle size={22} aria-hidden="true" />
              <h3>Não é diagnóstico</h3>
              <p>O resultado não confirma nem exclui diabetes e não define condutas médicas.</p>
            </article>
            <article data-reveal="up">
              <ListChecks size={22} aria-hidden="true" />
              <h3>Completude importa</h3>
              <p>Informações ausentes podem reduzir a confiabilidade da avaliação.</p>
            </article>
            <article data-reveal="up">
              <BrainCircuit size={22} aria-hidden="true" />
              <h3>Generalização limitada</h3>
              <p>Os métodos foram avaliados internamente em bases públicas, sem validação externa.</p>
            </article>
          </div>
        </section>

        <section className="auth-access-section" id="acesso" aria-labelledby="auth-access-title">
          <div className="auth-access-copy" data-reveal="left">
            <span className="auth-eyebrow">
              <LockKeyhole size={15} aria-hidden="true" />
              Entrada controlada
            </span>
            <h2 id="auth-access-title">Acesso profissional controlado</h2>
            <p>
              Entre com sua conta ou solicite um novo cadastro profissional. O
              acesso às avaliações é liberado após a validação do certificado
              profissional vinculado ao CRM informado.
            </p>
            <ul>
              <li><ShieldCheck size={17} aria-hidden="true" /> Conta individual e sessão protegida</li>
              <li><ShieldCheck size={17} aria-hidden="true" /> Verificação automática por PDF assinado</li>
              <li><ShieldCheck size={17} aria-hidden="true" /> Dados clínicos não persistidos no histórico</li>
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
                <small className="fieldset-note">Depois de confirmar o e-mail, assine um PDF de uso único com seu Certificado Digital do CFM para liberar as avaliações.</small>
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
              O HealthAI não substitui diagnóstico, exames, avaliação médica ou
              julgamento clínico.
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

            </>
          )}
          </section>

          </div>
        </section>

        <section className="auth-models-section auth-technical-section" id="transparencia" aria-labelledby="auth-models-title">
          <header className="auth-section-heading" data-reveal="left">
            <span>Transparência técnica</span>
            <h2 id="auth-models-title">Metodologia disponível para consulta.</h2>
            <p>
              O HealthAI utiliza métodos de aprendizado de máquina desenvolvidos
              com bases públicas de saúde. Informações sobre metodologia,
              desempenho e limitações estão disponíveis para consulta.
            </p>
          </header>

          <details
            className="auth-methodology auth-technical-details"
            data-reveal="scale"
            open={methodologyOpen}
            onToggle={(event) => setMethodologyOpen(event.currentTarget.open)}
          >
            <summary aria-expanded={methodologyOpen}>Consultar detalhes técnicos</summary>
            <div>
              <p className="technical-context-note">
                Estas informações descrevem o funcionamento técnico geral e não
                substituem a interpretação clínica individual.
              </p>
              <div className="auth-model-grid">
                <article>
                  <div className="auth-model-card-header">
                    <span><Database size={22} aria-hidden="true" /></span>
                    <div>
                      <small>Base Pima / OpenML 37</small>
                      <h3>Perfil para mulher adulta</h3>
                    </div>
                  </div>
                  <dl>
                    <div><dt>População</dt><dd>Mulheres adultas de herança indígena Pima.</dd></div>
                    <div><dt>Dados considerados</dt><dd>Gestações, glicose, pressão diastólica, prega cutânea, insulina, IMC, função de pedigree e idade.</dd></div>
                    <div><dt>Algoritmo utilizado</dt><dd>Random Forest.</dd></div>
                    <div><dt>Limitação</dt><dd>Teste interno da mesma fonte, sem validação externa.</dd></div>
                  </dl>
                  <div className="auth-model-metrics" aria-label="Métricas no teste interno da análise Pima">
                    <span><small>Recall</small><b>88,9%</b></span>
                    <span><small>F1-score</small><b>64,4%</b></span>
                    <span><small>AUC-ROC</small><b>82,5%</b></span>
                  </div>
                </article>

                <article>
                  <div className="auth-model-card-header">
                    <span><Gauge size={22} aria-hidden="true" /></span>
                    <div>
                      <small>NHANES / 2017–2018</small>
                      <h3>Perfil para adulto</h3>
                    </div>
                  </div>
                  <dl>
                    <div><dt>População</dt><dd>População adulta participante da onda NHANES 2017–2018.</dd></div>
                    <div><dt>Dados considerados</dt><dd>Sexo, idade, IMC, pressões sistólica e diastólica, hemoglobina glicada e glicose em jejum.</dd></div>
                    <div><dt>Algoritmo utilizado</dt><dd>SVM calibrado.</dd></div>
                    <div><dt>Limitação</dt><dd>Teste interno da própria onda, sem validação externa.</dd></div>
                  </dl>
                  <div className="auth-model-metrics" aria-label="Métricas no teste interno da análise NHANES">
                    <span><small>Recall</small><b>80,1%</b></span>
                    <span><small>F1-score</small><b>60,4%</b></span>
                    <span><small>AUC-ROC</small><b>90,1%</b></span>
                  </div>
                </article>
              </div>
              <div className="auth-methodology-copy">
                <p>
                  Os algoritmos candidatos foram comparados por F1 em validação
                  cruzada no conjunto de treino. O limiar foi definido por F2,
                  com maior peso para recall, e o desempenho final foi estimado
                  em uma partição de teste isolada da mesma fonte.
                </p>
                <p>
                  Ainda não foi realizada validação externa. As métricas descrevem
                  esses experimentos e não comprovam desempenho clínico em outras
                  populações.
                </p>
              </div>
            </div>
          </details>
        </section>
      </main>
      <PageFooter contact={privacy.contact} variant="public" />
    </div>
  );
}
