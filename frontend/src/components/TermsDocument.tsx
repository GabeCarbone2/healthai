import type { TermsInfo } from "../types";
import { formatBrazilianDate } from "../utils/date";

type Props = {
  info: TermsInfo;
  contact: string;
};

export function TermsDocument({ info, contact }: Props) {
  const effectiveDate = formatBrazilianDate(info.effective_date, "long");

  return (
    <article className="terms-document">
      <header>
        <span>Versão {info.version}</span>
        <span>Vigente desde {effectiveDate}</span>
      </header>

      <section>
        <h2>1. Finalidade e escopo</h2>
        <p>
          O HealthAI é uma ferramenta acadêmica de apoio à triagem que executa
          modelos de aprendizado de máquina sobre dados informados pelo usuário.
          O resultado não substitui diagnóstico, avaliação clínica, prescrição
          ou decisão médica.
        </p>
      </section>

      <section>
        <h2>2. Acesso profissional</h2>
        <p>
          O acesso às avaliações é destinado a profissionais médicos com conta
          individual, e-mail confirmado e cadastro profissional aprovado por
          análise administrativa manual. A aprovação no HealthAI não representa
          consulta automática ou certificação pelo CFM ou por conselho regional.
        </p>
      </section>

      <section>
        <h2>3. Responsabilidades do usuário</h2>
        <ul>
          <li>Manter credenciais pessoais e não compartilhar a sessão.</li>
          <li>Conferir os dados antes de solicitar o cálculo.</li>
          <li>Não inserir nome, CPF, prontuário ou outro identificador direto de paciente.</li>
          <li>Interpretar os resultados dentro do contexto clínico e das limitações exibidas.</li>
          <li>Não usar o sistema como única base para diagnóstico ou conduta.</li>
        </ul>
      </section>

      <section>
        <h2>4. Resultados e limitações</h2>
        <p>
          Probabilidades, limiares e explicações refletem os modelos e bases
          acadêmicas identificados na interface. Podem ocorrer erros, vieses,
          indisponibilidade e desempenho diferente em outras populações. A
          explicação individual mostra sensibilidade matemática, não causalidade.
        </p>
      </section>

      <section>
        <h2>5. Privacidade e segurança</h2>
        <p>
          O tratamento de dados segue o Aviso de Privacidade vigente. O usuário
          deve empregar somente códigos pseudonimizados e manter qualquer tabela
          de associação fora do HealthAI, protegida e com acesso restrito.
        </p>
      </section>

      <section>
        <h2>6. Disponibilidade e alterações</h2>
        <p>
          O serviço pode ser atualizado, interrompido ou descontinuado para
          manutenção, segurança ou evolução acadêmica. Alterações relevantes dos
          termos geram uma nova versão e exigem novo aceite antes das funções clínicas.
        </p>
      </section>

      <section>
        <h2>7. Encerramento e contato</h2>
        <p>
          O usuário pode excluir resultados e a própria conta pela interface. O
          acesso pode ser suspenso em caso de uso indevido, risco de segurança ou
          descumprimento destes termos. Dúvidas podem ser enviadas para{" "}
          <a href={`mailto:${contact}`}>{contact}</a>.
        </p>
      </section>
    </article>
  );
}
