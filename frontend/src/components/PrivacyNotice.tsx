import type { PrivacyInfo } from "../types";

type Props = {
  info: PrivacyInfo;
};

export function PrivacyNotice({ info }: Props) {
  return (
    <div className="privacy-notice">
      <section>
        <h3>Dados da conta</h3>
        <p>
          Nome, e-mail, CRM e UF são usados para administrar a conta e registrar
          a análise manual do cadastro profissional. A senha é armazenada
          somente como hash e a autenticação usa cookie protegido.
        </p>
      </section>
      <section>
        <h3>Dados das avaliações</h3>
        <p>
          Use apenas o identificador <code>PAC-…</code>. O HealthAI não armazena
          nome do paciente nem os valores clínicos enviados ao modelo. Conserva
          o código, resultado, versão do modelo e metadados de completude por até{" "}
          <strong>{info.result_retention_days} dias</strong>.
        </p>
      </section>
      <section>
        <h3>Cuidados e direitos</h3>
        <p>
          Pseudonimização não é anonimização. Mantenha a tabela de vínculo fora
          do HealthAI e com acesso restrito. Você pode excluir resultados ou a
          conta; o sistema é acadêmico e não realiza diagnóstico.
        </p>
      </section>
      <footer>
        <a href={`mailto:${info.contact}`}>{info.contact}</a>
        <span>Aviso {info.notice_version}</span>
      </footer>
    </div>
  );
}
