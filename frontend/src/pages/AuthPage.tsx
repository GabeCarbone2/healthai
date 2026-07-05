import {
  Activity,
  BrainCircuit,
  Eye,
  EyeOff,
  LockKeyhole,
  LogIn,
  MailCheck,
  Send,
  ShieldCheck,
  Sparkles,
  UserPlus,
} from "lucide-react";
import { FormEvent, useState } from "react";

import { login, register, resendVerification } from "../api";
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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [verificationEmailSent, setVerificationEmailSent] = useState(true);
  const [resending, setResending] = useState(false);
  const [resendNotice, setResendNotice] = useState("");

  function changeMode(nextMode: "login" | "register") {
    setMode(nextMode);
    setError("");
    setPassword("");
    setPasswordConfirmation("");
    setPrivacyAccepted(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (mode === "register" && password !== passwordConfirmation) {
      setError("As senhas não coincidem.");
      return;
    }
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
    <main className="auth-page">
      <div className="auth-atmosphere" aria-hidden="true">
        <span className="auth-orb orb-one" />
        <span className="auth-orb orb-two" />
        <span className="auth-orb orb-three" />
        <span className="auth-ring ring-one" />
        <span className="auth-ring ring-two" />
        <span className="auth-ribbon ribbon-one" />
        <span className="auth-ribbon ribbon-two" />
      </div>

      <header className="auth-topbar">
        <div className="auth-brand">
          <span>
            <Activity size={22} />
          </span>
          <div>
            <strong>HealthAI</strong>
            <small>Clinical intelligence</small>
          </div>
        </div>
        <div className="auth-security-note">
          <ShieldCheck size={15} />
          Acesso restrito a médicos
        </div>
      </header>

      <div className="auth-layout">
        <aside className="auth-intro">
          <div className="auth-eyebrow">
            <Sparkles size={15} />
            Inteligência aplicada à saúde
          </div>
          <h1>
            Plataforma de apoio clínico <em>para médicos.</em>
          </h1>
          <p>
            Explore modelos preditivos com rastreabilidade e privacidade em
            uma experiência criada para apoiar a prática médica.
          </p>
          <div className="auth-highlights">
            <span>
              <BrainCircuit size={17} />
              Modelos validados
            </span>
            <span>
              <ShieldCheck size={17} />
              Dados pseudonimizados
            </span>
            <span>
              <LockKeyhole size={17} />
              Acesso individual
            </span>
          </div>
        </aside>

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
              <Activity size={24} />
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
            {mode === "register" && (
              <>
                <label>
                  <span>Nome</span>
                  <input
                    type="text"
                    autoComplete="name"
                    minLength={2}
                    maxLength={120}
                    placeholder="Como devemos chamar você?"
                    required
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>
                <div className="professional-fields">
                  <label>
                    <span>CRM</span>
                    <input
                      type="text"
                      inputMode="numeric"
                      minLength={1}
                      maxLength={10}
                      pattern="[0-9]{1,10}"
                      placeholder="Somente números"
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
                      aria-label="UF do CRM"
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
                </div>
              </>
            )}

            <label>
              <span>E-mail</span>
              <input
                type="email"
                autoComplete="email"
                placeholder="voce@exemplo.com"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>

            <label>
              <span>Senha</span>
              <div className="password-input">
                <input
                  type={showPassword ? "text" : "password"}
                  aria-label="Senha"
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  minLength={8}
                  maxLength={128}
                  placeholder="Digite sua senha"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  title={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {mode === "register" && (
                <small>Mínimo de 8 caracteres</small>
              )}
            </label>

            {mode === "register" && (
              <>
                <label>
                  <span>Confirmar senha</span>
                  <input
                    type="password"
                    aria-label="Confirmar senha"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    placeholder="Repita sua senha"
                    required
                    value={passwordConfirmation}
                    onChange={(event) =>
                      setPasswordConfirmation(event.target.value)
                    }
                  />
                </label>
                <details className="registration-privacy">
                  <summary>Ler aviso de privacidade</summary>
                  <PrivacyNotice info={privacy} />
                </details>
                <label className="consent-check">
                  <input
                    type="checkbox"
                    required
                    checked={privacyAccepted}
                    onChange={(event) =>
                      setPrivacyAccepted(event.target.checked)
                    }
                  />
                  <span>
                    Li o aviso e consinto com o tratamento descrito.
                  </span>
                </label>
              </>
            )}

            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}

            <button className="auth-submit" disabled={loading}>
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
    </main>
  );
}
