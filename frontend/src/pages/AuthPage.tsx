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
  { id: "modelos", label: "Modelos" },
  { id: "privacidade", label: "Privacidade" },
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
          <aside className="auth-intro">
            <div className="auth-eyebrow">
              <Activity size={15} aria-hidden="true" />
              Apoio à triagem de risco de diabetes
            </div>
            <h1 id="auth-hero-title">
              Probabilidade sem contexto <em>é só ruído.</em>
            </h1>
            <p className="auth-description">
              O HealthAI organiza dados clínicos, aplica modelos de aprendizado
              de máquina e apresenta probabilidade, limiar, completude e
              limitações para apoiar a triagem de risco de diabetes.
            </p>
            <div className="auth-hero-actions">
              <a
                className="auth-hero-primary"
                href="#acesso"
                onClick={() => followSection("acesso", "login")}
              >
                Entrar no HealthAI
                <ArrowRight size={18} aria-hidden="true" />
              </a>
              <a
                className="auth-hero-secondary"
                href="#como-funciona"
                onClick={() => followSection("como-funciona")}
              >
                Conhecer como funciona
              </a>
            </div>
            <p className="auth-trust-line">
              <ShieldCheck size={16} aria-hidden="true" />
              Apoio responsável, acesso profissional e dados pseudonimizados
            </p>
          </aside>

          <div className="auth-signal-stage" aria-hidden="true">
            <div className="auth-signal-index">
              <span>Representação conceitual</span>
              <b>Não é resultado de paciente</b>
            </div>
            <div className="auth-result-structure">
              <div className="auth-result-row probability">
                <span>Probabilidade estimada</span>
                <i><b /></i>
              </div>
              <div className="auth-result-row threshold">
                <span>Limiar aplicado</span>
                <i><b /></i>
              </div>
              <div className="auth-result-row completeness">
                <span>Completude dos dados</span>
                <i>
                  <b />
                  <b />
                  <b />
                  <b />
                  <b />
                </i>
              </div>
            </div>
            <div className="auth-signal-legend">
              <span>Exemplo visual da estrutura do resultado</span>
              <span>Sem monitoramento em tempo real</span>
            </div>
          </div>
          </div>
        </section>

        <section className="auth-feature-section" id="como-funciona" aria-labelledby="auth-features-title">
          <header className="auth-section-heading">
            <span>Como funciona</span>
            <h2 id="auth-features-title">A estimativa vem acompanhada de evidências.</h2>
            <p>
              Cada resultado apresenta a origem do modelo, o limiar usado, a
              completude dos dados e as limitações relevantes para sua leitura.
            </p>
          </header>
          <div className="auth-feature-grid">
            <article>
              <span><BrainCircuit size={24} aria-hidden="true" /></span>
              <small>01 / Contexto do modelo</small>
              <h3>Perfis não se misturam</h3>
              <p>Cada modelo utiliza sua própria população, conjunto de variáveis e limitações.</p>
            </article>
            <article>
              <span><ShieldCheck size={24} aria-hidden="true" /></span>
              <small>02 / Dados mínimos</small>
              <h3>O formulário termina na inferência</h3>
              <p>Os valores clínicos utilizados no cálculo não são armazenados no histórico.</p>
            </article>
            <article>
              <span><LockKeyhole size={24} aria-hidden="true" /></span>
              <small>03 / Leitura do resultado</small>
              <h3>Limiar à vista, incerteza também</h3>
              <p>O resultado apresenta probabilidade, limiar aplicado, completude dos dados e limitações.</p>
            </article>
          </div>
        </section>

        <section className="auth-models-section" id="modelos" aria-labelledby="auth-models-title">
          <header className="auth-section-heading">
            <span>Modelos e populações</span>
            <h2 id="auth-models-title">Duas bases, dois contextos de leitura.</h2>
            <p>
              Pima e NHANES são experimentos independentes. As métricas abaixo
              vêm do teste interno de cada fonte e não representam validação clínica.
            </p>
          </header>

          <div className="auth-model-grid">
            <article>
              <div className="auth-model-card-header">
                <span><Database size={22} aria-hidden="true" /></span>
                <div>
                  <small>Base Pima / OpenML 37</small>
                  <h3>Pima — mulheres adultas</h3>
                </div>
              </div>
              <dl>
                <div>
                  <dt>População</dt>
                  <dd>Mulheres adultas de herança indígena Pima.</dd>
                </div>
                <div>
                  <dt>Variáveis</dt>
                  <dd>Gestações, glicose, pressão diastólica, prega cutânea, insulina, IMC, função de pedigree e idade.</dd>
                </div>
                <div>
                  <dt>Modelo selecionado</dt>
                  <dd>Random Forest.</dd>
                </div>
                <div>
                  <dt>Principal limitação</dt>
                  <dd>Avaliação em teste interno da mesma fonte, sem validação externa.</dd>
                </div>
              </dl>
              <div className="auth-model-metrics" aria-label="Métricas no teste interno do modelo Pima">
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
                  <h3>NHANES — adultos</h3>
                </div>
              </div>
              <dl>
                <div>
                  <dt>População</dt>
                  <dd>População adulta participante da onda NHANES 2017–2018.</dd>
                </div>
                <div>
                  <dt>Variáveis</dt>
                  <dd>Sexo, idade, IMC, pressões sistólica e diastólica, hemoglobina glicada e glicose em jejum.</dd>
                </div>
                <div>
                  <dt>Modelo selecionado</dt>
                  <dd>SVM calibrado.</dd>
                </div>
                <div>
                  <dt>Principal limitação</dt>
                  <dd>Avaliação em teste interno da própria onda, sem validação externa.</dd>
                </div>
              </dl>
              <div className="auth-model-metrics" aria-label="Métricas no teste interno do modelo NHANES">
                <span><small>Recall</small><b>80,1%</b></span>
                <span><small>F1-score</small><b>60,4%</b></span>
                <span><small>AUC-ROC</small><b>90,1%</b></span>
              </div>
            </article>
          </div>

          <details
            className="auth-methodology"
            open={methodologyOpen}
            onToggle={(event) => setMethodologyOpen(event.currentTarget.open)}
          >
            <summary aria-expanded={methodologyOpen}>Ver metodologia</summary>
            <div>
              <p>
                Os candidatos foram comparados por F1 em validação cruzada no
                conjunto de treino. O limiar foi definido por F2, com maior peso
                para recall, e o desempenho final foi estimado em uma partição
                de teste isolada da mesma fonte.
              </p>
              <p>
                Ainda não foi realizada validação externa. Por isso, os números
                descrevem estes experimentos e não comprovam desempenho clínico
                em outras populações.
              </p>
            </div>
          </details>
        </section>

        <section className="auth-privacy-section" id="privacidade" aria-labelledby="auth-privacy-title">
          <header className="auth-section-heading">
            <span>Transparência e privacidade</span>
            <h2 id="auth-privacy-title">O mínimo necessário, com rastreabilidade.</h2>
            <p>
              O histórico mantém o resultado e seus metadados de leitura, sem
              conservar os valores clínicos enviados ao modelo.
            </p>
          </header>
          <ol className="auth-privacy-list">
            <li>
              <span><Database size={22} aria-hidden="true" /></span>
              <div>
                <small>01</small>
                <h3>Dados clínicos somente no cálculo</h3>
                <p>Os valores informados são utilizados na inferência e não são persistidos no histórico.</p>
              </div>
            </li>
            <li>
              <span><Fingerprint size={22} aria-hidden="true" /></span>
              <div>
                <small>02</small>
                <h3>Identificador pseudonimizado</h3>
                <p>O histórico é associado a um código <code>PAC-…</code>. Pseudonimização não é anonimização.</p>
              </div>
            </li>
            <li>
              <span><ListChecks size={22} aria-hidden="true" /></span>
              <div>
                <small>03</small>
                <h3>Resultado rastreável</h3>
                <p>Probabilidade, limiar, modelo, versão e completude acompanham cada registro.</p>
              </div>
            </li>
          </ol>
        </section>

        <section className="auth-access-section" id="acesso" aria-labelledby="auth-access-title">
          <div className="auth-access-copy">
            <span className="auth-eyebrow">
              <LockKeyhole size={15} aria-hidden="true" />
              Entrada controlada
            </span>
            <h2 id="auth-access-title">Acesso profissional controlado</h2>
            <p>
              Entre com sua conta ou solicite um novo cadastro profissional. O
              acesso às avaliações depende da análise administrativa do CRM
              informado.
            </p>
            <ul>
              <li><ShieldCheck size={17} aria-hidden="true" /> Conta individual e sessão protegida</li>
              <li><ShieldCheck size={17} aria-hidden="true" /> Conferência administrativa do cadastro profissional</li>
              <li><ShieldCheck size={17} aria-hidden="true" /> Dados clínicos não persistidos no histórico</li>
            </ul>
          </div>

          <div className="auth-access">
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
                <small className="fieldset-note">O CRM informado é submetido à conferência administrativa antes da liberação das avaliações.</small>
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
              O HealthAI é uma ferramenta de apoio à triagem e não substitui
              diagnóstico, avaliação médica ou decisão clínica.
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
      </main>
      <PageFooter contact={privacy.contact} variant="public" />
    </div>
  );
}
