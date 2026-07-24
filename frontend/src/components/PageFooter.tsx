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
      <footer className="page-footer public-footer" data-reveal="up">
        <div className="public-footer-grid">
          <div className="public-footer-brand">
            <span aria-hidden="true">
              <HealthAiLogo className="healthai-logo" />
            </span>
            <div>
              <strong>HealthAI</strong>
              <p>
                Plataforma de apoio à triagem de risco de diabetes.
              </p>
            </div>
          </div>
          <nav aria-label="Navegação do rodapé">
            <strong>Plataforma</strong>
            <a href="#como-funciona">Como funciona</a>
            <a href="#seguranca">Segurança e privacidade</a>
            <a href="#limitacoes">Limitações</a>
            <a href="#transparencia">Transparência técnica</a>
            <a href="/terms">Termos de uso</a>
            <a href={contactHref}>Contato</a>
            <a href="#acesso">Acesso</a>
          </nav>
          <div className="public-footer-contact">
            <strong>Contato</strong>
            <p>Dúvidas sobre a plataforma, privacidade ou exercício de direitos?</p>
            <a href={contactHref} title={`Canal de privacidade: ${contact}`}>
              {contact}
            </a>
          </div>
        </div>
        <div className="public-footer-bottom">
          <span>HealthAI v{packageInfo.version}</span>
          <span>O HealthAI não substitui diagnóstico, exames, avaliação médica ou julgamento clínico.</span>
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
