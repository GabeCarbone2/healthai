import type { PrivacyInfo } from "../types";

type Props = {
  info: PrivacyInfo;
};

export function PrivacyNotice({ info }: Props) {
  return (
    <div className="privacy-notice">
      <p>
        O HealthAI usa seu nome, e-mail, CRM e UF do registro para administrar
        a conta profissional. Senhas são armazenadas somente como hash e a
        autenticação usa cookie protegido.
      </p>
      <p>
        Nas avaliações, use apenas o identificador <code>PAC-…</code>. O
        sistema não armazena o nome do paciente nem os valores clínicos
        enviados ao modelo; conserva o código pseudonimizado e o resultado por
        até <strong>{info.result_retention_days} dias</strong>.
      </p>
      <p>
        Pseudonimização não é anonimização. Mantenha qualquer tabela que ligue o
        código à pessoa fora do HealthAI, com acesso restrito. O sistema tem
        finalidade acadêmica e não realiza diagnóstico.
      </p>
      <p>
        Você pode apagar resultados individualmente ou excluir a conta e seus
        dados. Canal de privacidade: <strong>{info.contact}</strong>.
      </p>
      <small>Versão do aviso: {info.notice_version}</small>
    </div>
  );
}
