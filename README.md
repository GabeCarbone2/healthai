# HealthAI

Projeto de Trabalho de Conclusão de Curso (TCC) para investigar o uso de
machine learning na **predição de risco de diabetes** a partir de dados
clínicos tabulares.

> O sistema tem finalidade acadêmica e de apoio à pesquisa. Sua saída não é
> diagnóstico médico e não substitui avaliação de um profissional de saúde.

## Objetivos

- construir um pipeline reproduzível de preparação, treino e avaliação;
- comparar um baseline interpretável com outros algoritmos de classificação;
- priorizar métricas adequadas ao problema, especialmente *recall* e ROC-AUC;
- documentar limitações, vieses e cuidados éticos com dados de saúde.

## Estrutura

```text
HEALTHAI/
├── configs/              # Parâmetros dos experimentos
├── data/                 # Dados brutos, intermediários e processados
├── docs/                 # Metodologia e documentação do TCC
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

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Coloque o conjunto de dados CSV em `data/raw/diabetes.csv`. O esquema inicial
esperado está em [`data/README.md`](data/README.md). Em seguida:

```bash
make train
make test
```

O treinamento salva o pipeline em `models/diabetes_pipeline.joblib` e as
métricas em `reports/metrics.json`.

Para gerar previsões em lote:

```bash
healthai-predict --input data/processed/pacientes.csv \
  --output reports/predictions.csv
```

## Fluxo de trabalho sugerido

1. Registrar origem, licença e dicionário dos dados.
2. Fazer análise exploratória sem alterar os dados brutos.
3. Definir uma divisão de treino e teste antes de comparar modelos.
4. Treinar o baseline e registrar as métricas.
5. Comparar modelos com validação cruzada e ajuste de hiperparâmetros.
6. Analisar explicabilidade, viés, limitações e validade externa.

