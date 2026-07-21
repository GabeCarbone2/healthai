import packageInfo from "../../package.json";
import { HealthAiLogo } from "./HealthAiLogo";

type Props = {
  contact: string;
  variant?: "public" | "internal";
};

export function PageFooter({ contact, variant = "internal" }: Props) {
  const contactHref = `mailto:${contact}`;

  if (variant === "public") {
    return (
      <footer className="page-footer public-footer">
        <div className="public-footer-grid">
          <div className="public-footer-brand">
            <span aria-hidden="true">
              <HealthAiLogo className="healthai-logo" />
            </span>
            <div>
              <strong>HealthAI</strong>
              <p>
                Apoio acadêmico à triagem de risco de diabetes com transparência,
                privacidade e responsabilidade.
              </p>
            </div>
          </div>
          <nav aria-label="Links da plataforma">
            <strong>Plataforma</strong>
            <a href="/">Acesso profissional</a>
            <a href="/terms">Termos de Uso</a>
          </nav>
          <div className="public-footer-contact">
            <strong>Privacidade</strong>
            <p>Dúvidas sobre dados pessoais ou exercício de direitos?</p>
            <a href={contactHref} title={`Canal de privacidade: ${contact}`}>
              {contact}
            </a>
          </div>
        </div>
        <div className="public-footer-bottom">
          <span>HealthAI v{packageInfo.version} · Ferramenta acadêmica</span>
          <span>Não substitui diagnóstico, avaliação ou decisão médica.</span>
        </div>
      </footer>
    );
  }

  return (
    <footer className="page-footer internal-footer">
      <span>HealthAI v{packageInfo.version}</span>
      <span aria-hidden="true">•</span>
      <span>Ferramenta acadêmica</span>
      <span aria-hidden="true">•</span>
      <span>Não substitui diagnóstico médico</span>
      <span aria-hidden="true">•</span>
      <a href="/terms">Termos de Uso</a>
      <span aria-hidden="true">•</span>
      <a href={contactHref} title={`Canal de privacidade: ${contact}`}>Privacidade</a>
    </footer>
  );
}
