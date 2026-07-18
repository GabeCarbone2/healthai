# HealthAI

Projeto de Trabalho de Conclusão de Curso (TCC) para investigar o uso de
machine learning na **predição de risco de diabetes** a partir de dados
clínicos tabulares.

> O sistema tem finalidade acadêmica e de apoio à pesquisa. Sua saída não é
> diagnóstico médico e não substitui avaliação de um profissional de saúde.

## Objetivos

- construir um pipeline reproduzível de preparação, treino e avaliação;
- comparar Regressão Logística, Random Forest e SVM;
- permitir uma comparação posterior com métodos de Gradient Boosting;
- priorizar métricas adequadas ao problema, especialmente *recall* e ROC-AUC;
- documentar limitações, vieses e cuidados éticos com dados de saúde.

## Conjuntos de dados

O estudo prevê o uso do **Pima Indians Diabetes Dataset** e do **NHANES**. O
[`dicionario_variaveis_healthai.csv`](dicionario_variaveis_healthai.csv) mapeia
as variáveis clínicas entre as duas bases e registra diferenças de medição que
precisam ser preservadas durante o pré-processamento.

Os dados públicos podem ser baixados e harmonizados de forma reproduzível com:

```bash
make data
```

Esse comando gera:

- `data/raw/diabetes.csv`: Pima no esquema original do primeiro baseline;
- `data/processed/pima_diabetes.csv`: Pima harmonizado;
- `data/processed/nhanes_2017_2018.csv`: módulos NHANES unidos por participante;
- `healthai_dados_publicos.csv`: união das duas bases com a origem preservada.

O treinamento usa `healthai_dados_publicos.csv`, mas cria experimentos
separados por origem. O desfecho Pima e o autorrelato de diagnóstico do NHANES
possuem definições diferentes e não são combinados em um único modelo.

## Estrutura

```text
HEALTHAI/
├── backend/              # API FastAPI para inferência
├── configs/              # Parâmetros dos experimentos
├── data/                 # Dados brutos, intermediários e processados
├── docs/                 # Metodologia e documentação do TCC
├── frontend/             # Interface React e TypeScript
├── models/               # Modelos treinados (não versionados)
├── notebooks/            # Exploração e experimentos
├── reports/              # Métricas, tabelas e figuras
├── src/healthai/         # Código-fonte reutilizável
├── tests/                # Testes automatizados
├── Makefile              # Atalhos para tarefas comuns
└── pyproject.toml         # Dependências e configuração do projeto
```

Veja a descrição detalhada em [`docs/estrutura.md`](docs/estrutura.md).

## Início rápido

Requer Python 3.10 ou superior e Node.js 20 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
npm --prefix frontend install
```

Baixe e prepare os dados e, em seguida, treine os modelos:

```bash
make data
make train
make test
```

`make test` executa os testes do backend e do frontend. Durante o
desenvolvimento da interface, use `npm --prefix frontend run test:watch` para
manter o Vitest em modo interativo. O workflow `.github/workflows/ci.yml`
repete testes, lint, build e verificação das migrações em pushes e pull
requests.

## Interface web

Com os modelos treinados, inicie API e frontend em terminais separados:

```bash
make api
```

```bash
make frontend
```

A interface fica disponível em `http://127.0.0.1:5173` e a documentação
interativa da API em `http://127.0.0.1:8000/docs`. A API valida faixas,
completude e populações aceitas pelos modelos. Ela persiste o identificador
pseudonimizado `PAC-…`, resultado, versão do modelo e metadados de completude;
nomes de pacientes e valores clínicos enviados ao modelo não são armazenados.

No primeiro acesso, use **Criar conta**. O cadastro profissional exige CRM e
UF e impede a repetição desse par. Após confirmar o e-mail, a conta permanece
com o CRM pendente e só recebe acesso às avaliações depois da aprovação manual
por um administrador. A API registra o status, a data, o administrador
responsável e eventual motivo de rejeição. A consulta é feita no portal público
do CFM, sem automação pelo HealthAI. Cada decisão administrativa também é
preservada em uma trilha de auditoria imutável.

Defina uma ou mais contas administrativas, separadas por vírgula, antes de
iniciar a API:

```bash
HEALTHAI_ADMIN_EMAILS=administrador@example.com
```

Contas existentes com esses e-mails são promovidas na inicialização. A API cria
automaticamente o banco SQLite `data/healthai.db`, armazena usuários, sessões e
o histórico de resultados, e protege senhas com Argon2. A conta só abre uma
sessão depois da confirmação do e-mail; o link de confirmação expira em 24
horas e somente hashes de tokens são persistidos. A recuperação de senha usa
resposta genérica contra enumeração, link de uso único válido por uma hora e
encerra as sessões anteriores depois da redefinição. A sessão usa cookie
`HttpOnly` de sessão e expira após 30 minutos sem atividade. Os valores clínicos
dos formulários não são gravados.
Ao iniciar, a API aplica automaticamente as migrações pendentes do Alembic.
Resultados vencidos são eliminados conforme
`HEALTHAI_RESULT_RETENTION_DAYS` (180 dias por padrão), e o usuário pode excluir
seu histórico ou a conta inteira. Os Termos de Uso são públicos, versionados e
um novo aceite é exigido quando a versão muda. Uma rotina periódica remove resultados,
sessões e links de autenticação expirados. Consulte o
[aviso de privacidade](docs/privacidade.md) e configure
`HEALTHAI_PRIVACY_CONTACT` antes de publicar o sistema.

Para aplicar as migrações manualmente ou gerar uma nova revisão após alterar os
modelos do banco:

```bash
make migrate
make migration message="descricao da alteracao"
```

As opções de ambiente estão documentadas em `.env.example`. Em uma publicação
HTTPS, defina `HEALTHAI_SECURE_COOKIE=true` e configure
`HEALTHAI_DATABASE_URL` para o banco do ambiente.
Copie `.env.example` para `.env`; a API carrega esse arquivo automaticamente.
Em produção, copie `.env.production.example` para `.env.production`. A API
recusa a inicialização se HTTPS, SMTP, administrador ou canal de privacidade
estiverem incompletos.

A camada de persistência possui índices voltados às consultas reais, pool de
conexões configurável e roteamento opcional para múltiplas read replicas
PostgreSQL. O deploy SQLite mantém as leituras no primário. Consulte
[`docs/escalabilidade.md`](docs/escalabilidade.md) para ativação, limites do
pool, consistência eventual e critérios para cache/CDN.

Para enviar confirmações reais pela caixa postal da Hostinger, crie o endereço
remetente no hPanel e configure:

```bash
HEALTHAI_EMAIL_DELIVERY=smtp
HEALTHAI_SMTP_HOST=smtp.hostinger.com
HEALTHAI_SMTP_PORT=465
HEALTHAI_SMTP_SECURITY=ssl
HEALTHAI_SMTP_USERNAME=nao-responda@seu-dominio.com
HEALTHAI_SMTP_PASSWORD=senha-da-caixa-postal
HEALTHAI_EMAIL_FROM=HealthAI <nao-responda@seu-dominio.com>
HEALTHAI_FRONTEND_URL=https://seu-frontend.example
```

Também é possível usar STARTTLS com a porta 587. A senha SMTP deve existir
somente no `.env` local ou no ambiente seguro do servidor.
No modo padrão `console`, adequado ao desenvolvimento, links de confirmação e
recuperação são exibidos no log da API e nenhum e-mail externo é enviado.

O treinamento separa o teste antes de comparar os três algoritmos, executa
busca aleatória de hiperparâmetros com validação cruzada somente no treino,
aprende um limiar F2 com previsões out-of-fold e cria os modelos finais
`models/pima_selected.joblib` e `models/nhanes_selected.joblib`. As métricas
ficam em `reports/model_comparison.json`, incluindo Brier score, pontos da
curva de calibração, intervalos bootstrap de 95%, métricas por subgrupos,
resumo de disparidades, explicabilidade por permutação e estado da validação
externa. As curvas renderizadas ficam em
`reports/figures/pima_calibration.png` e
`reports/figures/nhanes_calibration.png`; as importâncias ficam em
`reports/figures/pima_feature_importance.png` e
`reports/figures/nhanes_feature_importance.png`.

Com cinco folds e F1 como critério de seleção, o ajuste resultou em:

- Pima: Random Forest, F1 médio de 68,34% (desvio de 2,82%);
- NHANES: SVM, F1 médio de 71,52% (desvio de 1,43%).

Os limiares F2 definidos apenas no treino foram 21% para Pima e 13% para
NHANES. No teste isolado, os respectivos recalls foram 88,89% e 80,11%. O
teste não participa do ajuste, da escolha do algoritmo nem do limiar.

A discussão de explicabilidade, validação externa, viés e limitações está
consolidada em [`docs/modelo.md`](docs/modelo.md). A validação externa
verdadeira ainda está marcada como não realizada, pois exige uma coorte
independente compatível com as mesmas variáveis e definição de desfecho.
Na API interativa, cada nova predição também recebe uma explicação efêmera por
substituição individual pela referência imputada do pipeline. Ela mede
sensibilidade local, não é causal ou aditiva e não é armazenada no histórico.

Para gerar previsões em lote:

```bash
healthai-predict --input data/processed/pima_diabetes.csv \
  --model models/pima_selected.joblib \
  --output reports/predictions.csv
```

## Fluxo de trabalho sugerido

1. Registrar origem, licença e dicionário dos dados.
2. Fazer análise exploratória sem alterar os dados brutos.
3. Definir uma divisão de treino e teste antes de comparar modelos.
4. Treinar Regressão Logística, Random Forest e SVM e registrar as métricas.
5. Comparar os modelos com validação cruzada e ajuste de hiperparâmetros.
6. Definir o limiar com previsões out-of-fold e objetivo F2.
7. Avaliar posteriormente métodos de Gradient Boosting.
8. Analisar explicabilidade, viés, limitações e validade externa.
