import { FileText } from "lucide-react";

import { HealthAiLogo } from "../components/HealthAiLogo";
import { PageFooter } from "../components/PageFooter";
import { TermsDocument } from "../components/TermsDocument";
import type { PrivacyInfo, TermsInfo } from "../types";

type Props = { info: TermsInfo; privacy: PrivacyInfo };

export function TermsPage({ info, privacy }: Props) {
  return (
    <main className="legal-page">
      <header className="legal-topbar">
        <a href="/" aria-label="Voltar ao HealthAI">
          <HealthAiLogo className="healthai-logo" />
          <strong>HealthAI</strong>
        </a>
      </header>
      <div className="legal-layout">
        <header className="legal-heading">
          <FileText size={30} aria-hidden="true" />
          <span className="page-eyebrow">Documento público</span>
          <h1>Termos de Uso</h1>
          <p>Condições para acesso e utilização responsável do HealthAI.</p>
        </header>
        <TermsDocument info={info} contact={privacy.contact} />
      </div>
      <PageFooter contact={privacy.contact} variant="public" />
    </main>
  );
}
