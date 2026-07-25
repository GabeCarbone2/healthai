# Aviso de privacidade e controles LGPD

Versão do aviso: **2026-07-25.1**

Este documento descreve os controles técnicos implementados no HealthAI. Ele
não substitui a definição, pelo responsável pelo projeto, do controlador, do
encarregado, da hipótese legal aplicável e dos procedimentos institucionais de
atendimento aos titulares.

## Finalidade

O HealthAI trata dados para autenticar usuários e executar, com finalidade
acadêmica, classificações dos desfechos de diabetes observados nas bases. A
saída não representa risco futuro validado, não é diagnóstico e não substitui
avaliação profissional.

## Dados tratados

- conta profissional: nome, e-mail, CRM, UF do CRM, estado e data da
  verificação, hashes SHA-256 do certificado e do documento assinado,
  desafios efêmeros, estado da confirmação do e-mail, hash da senha, sessões e
  data/versionamento dos aceites do aviso e dos Termos de Uso;
- avaliação: identificador pseudonimizado `PAC-…`, modelo e sua versão,
  resultado, probabilidade, limiar, completude da entrada, quantidade de
  medidas imputadas e data;
- dados clínicos informados no formulário: processados transitoriamente para
  inferência e não persistidos pelo aplicativo.
- PDF de comprovação profissional: processado transitoriamente para validar a
  assinatura e não persistido pelo aplicativo.

O sistema não deve receber nome, CPF, número de prontuário ou outro
identificador direto do paciente. A eventual tabela que relacione o código
`PAC-…` à pessoa deve permanecer fora do HealthAI, protegida e acessível apenas
a pessoas autorizadas.

Pseudonimização não equivale a anonimização. Se o código puder ser relacionado
novamente a uma pessoa, os dados continuam sujeitos à LGPD.

## Consentimento e responsabilidade

O cadastro exige aceite livre e destacado da versão atual deste aviso. O
usuário pode recusar o aceite e sair, ou excluir a conta. Quando o aviso muda,
um novo aceite é exigido antes do acesso aos modelos e resultados.

O CRM é comprovado por um PDF de uso único assinado com certificado digital
profissional. O HealthAI valida a assinatura PAdES, a cadeia de confiança
ICP-Brasil, o estado de revogação, a integridade do documento e a
correspondência dos atributos CRM e UF do certificado com a conta. Cada
aprovação fica registrada em uma trilha de auditoria sem exigir conta
administrativa. Enquanto estiver pendente, o usuário pode administrar sua
conta, mas não acessar avaliações ou resultados clínicos.

Essa verificação demonstra a posse de um certificado profissional válido no
momento da assinatura. Ela não consulta em tempo real eventual suspensão,
cancelamento ou outra alteração cadastral no portal do CFM ou do CRM.

O aceite do usuário da conta não representa, por si só, consentimento do
paciente nem define a hipótese legal para tratar dados de saúde de terceiros.
Antes de uso fora do ambiente acadêmico controlado, o responsável pelo projeto
deve documentar a hipótese legal adequada, as funções de controlador e
operador, o canal do encarregado e, quando aplicável, o consentimento do
titular.

## Retenção e eliminação

Resultados são mantidos por até `HEALTHAI_RESULT_RETENTION_DAYS` dias
(180 por padrão). Uma rotina periódica elimina registros vencidos, sessões e
links de confirmação, recuperação e desafios profissionais expirados; a
limpeza também é executada na inicialização e ao acessar ou criar resultados.
O evento de aprovação mantém apenas a impressão digital do documento como
evidência. Dados da conta permanecem enquanto ela estiver ativa.

O usuário pode:

- excluir um resultado;
- apagar todo o histórico;
- excluir permanentemente a conta, suas sessões e todos os resultados,
  mediante confirmação da senha.

Backups, quando existentes, precisam ter política própria de expiração e
eliminação documentada pelo responsável pela infraestrutura.

## Compartilhamento e segurança

Resultados e dados clínicos não são enviados ao provedor de e-mail. Quando a
entrega SMTP está habilitada, nome e endereço de e-mail da conta são
compartilhados com a Hostinger exclusivamente para enviar a confirmação
transacional. O responsável pelo projeto deve documentar esse operador e seus
termos no registro das operações de tratamento.

As senhas usam hash Argon2; links de confirmação e recuperação armazenam somente
o hash do token. O link de recuperação expira em uma hora, é de uso único e sua
utilização encerra todas as sessões existentes. As sessões usam tokens opacos em cookies `HttpOnly`, e o cookie deve ser
marcado automaticamente como seguro quando `HEALTHAI_ENV=production`. A
publicação deve usar HTTPS, controle de acesso,
backup protegido, registro de incidentes e revisão periódica de permissões.

## Direitos e contato

O titular pode solicitar informação, acesso, correção, bloqueio, anonimização
ou eliminação quando aplicável. Configure o canal responsável em
`HEALTHAI_PRIVACY_CONTACT`; o valor de exemplo não deve ser usado em produção.
