import { ChevronDown } from "lucide-react";
import { ReactNode, useState } from "react";

import type { PrivacyInfo } from "../types";

type Props = {
  info: PrivacyInfo;
};

type PrivacySectionProps = {
  title: string;
  children: ReactNode;
};

function PrivacySection({ title, children }: PrivacySectionProps) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="privacy-accordion"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary aria-expanded={open}>
        <span>{title}</span>
        <ChevronDown size={17} aria-hidden="true" />
      </summary>
      <div>{children}</div>
    </details>
  );
}

export function PrivacyNotice({ info }: Props) {
  return (
    <div className="privacy-notice">
      <PrivacySection title="Como os dados são usados">
        <p>
          Nome, e-mail, CRM e UF são usados para administrar a conta e registrar
          a análise manual do cadastro profissional. A senha é armazenada
          somente como hash e a autenticação usa cookie protegido.
        </p>
      </PrivacySection>
      <PrivacySection title="Dados armazenados">
        <p>
          O HealthAI conserva o identificador <code>PAC-…</code>, resultado,
          probabilidade, limiar, versão do modelo e metadados de completude.
        </p>
      </PrivacySection>
      <PrivacySection title="Dados não armazenados">
        <p>
          O sistema não armazena nome, CPF ou prontuário do paciente nem os valores
          clínicos enviados ao modelo.
        </p>
      </PrivacySection>
      <PrivacySection title="Pseudonimização">
        <p>
          Pseudonimização não é anonimização. Mantenha a tabela de vínculo fora
          do HealthAI e com acesso restrito. Use somente um identificador no formato
          <code> PAC-…</code> nas avaliações.
        </p>
      </PrivacySection>
      <PrivacySection title="Retenção">
        <p>
          Prazo de retenção dos resultados: até <strong>{info.result_retention_days} dias</strong>.
          Depois desse período, os registros são removidos conforme a configuração
          informada pelo sistema.
        </p>
      </PrivacySection>
      <PrivacySection title="Direitos do usuário">
        <p>
          Você pode excluir resultados individuais, limpar o histórico ou excluir
          permanentemente a conta e seus dados associados pela própria interface.
        </p>
      </PrivacySection>
      <PrivacySection title="Canal de privacidade">
        <p>
          Para dúvidas sobre privacidade, escreva para{" "}
          <a href={`mailto:${info.contact}`}>{info.contact}</a>.
        </p>
      </PrivacySection>
      <footer>
        <span>Aviso {info.notice_version}</span>
      </footer>
    </div>
  );
}
