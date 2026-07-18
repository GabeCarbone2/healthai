import packageInfo from "../../package.json";

type Props = {
  contact: string;
  variant?: "public" | "internal";
};

export function PageFooter({ contact, variant = "internal" }: Props) {
  const contactHref = `mailto:${contact}`;

  if (variant === "public") {
    return (
      <footer className="page-footer public-footer">
        <span>HealthAI v{packageInfo.version}</span>
        <span aria-hidden="true">•</span>
        <span>Uso acadêmico</span>
        <span aria-hidden="true">•</span>
        <a href="/terms">Termos de Uso</a>
        <span aria-hidden="true">•</span>
        <a href={contactHref}>Contato e privacidade</a>
      </footer>
    );
  }

  return (
    <footer className="page-footer internal-footer">
      <span>HealthAI v{packageInfo.version}</span>
      <span aria-hidden="true">•</span>
      <span>Uso acadêmico</span>
      <span aria-hidden="true">•</span>
      <a href="/terms">Termos de Uso</a>
      <span aria-hidden="true">•</span>
      <a href={contactHref}>Privacidade: {contact}</a>
    </footer>
  );
}
