import { Activity, CircleAlert, MailCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { verifyEmail } from "../api";
import type { User } from "../types";

type Props = {
  token: string;
  onVerified: (user: User) => void;
};

export function VerifyEmailPage({ token, onVerified }: Props) {
  const started = useRef(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!token) {
      setError("O link de verificação está incompleto.");
      return;
    }
    verifyEmail(token)
      .then(onVerified)
      .catch((requestError) => {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Não foi possível confirmar seu e-mail.",
        );
      });
  }, [onVerified, token]);

  return (
    <main className="email-verification-page">
      <section className="email-verification-card">
        <span className={error ? "verification-error-icon" : ""}>
          {error ? <CircleAlert size={34} /> : <MailCheck size={34} />}
        </span>
        <small>HealthAI</small>
        <h1>{error ? "Link não confirmado" : "Confirmando seu e-mail"}</h1>
        <p>
          {error
            ? error
            : "Só um instante. Estamos ativando sua conta com segurança."}
        </p>
        {!error && <Activity className="verification-spinner" size={24} />}
        {error && (
          <a className="auth-submit" href="/">
            Voltar para entrar
          </a>
        )}
      </section>
    </main>
  );
}
