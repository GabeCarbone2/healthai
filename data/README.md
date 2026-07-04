# Dados

Os arquivos de pacientes não devem ser enviados ao Git. A pasta mantém apenas
este dicionário e marcadores vazios.

## Diretórios

- `raw/`: cópia imutável dos dados obtidos na fonte;
- `interim/`: resultados intermediários de limpeza;
- `processed/`: dados finais usados pelos modelos;
- `external/`: documentação ou dados auxiliares públicos.

## Dados públicos usados

- Pima: OpenML, conjunto `diabetes`, ID 37. A cópia original fica em
  `raw/pima/openml_diabetes.csv`.
- NHANES: ciclo 2017–2018 do CDC. Os módulos XPT originais ficam em
  `raw/nhanes_2017_2018/`.

Execute `make data` para reproduzir o download e gerar:

- `raw/diabetes.csv`, compatível com o pipeline atual;
- `processed/pima_diabetes.csv`;
- `processed/nhanes_2017_2018.csv`;
- `../healthai_dados_publicos.csv`, com as duas fontes e 26 colunas
  harmonizadas.

Nenhum valor clínico é sintetizado. Zeros fisiologicamente implausíveis do
Pima são preservados na cópia bruta e convertidos em ausentes apenas na versão
processada. No NHANES, valores não medidos ou respostas não classificáveis
permanecem ausentes.

## Esquema inicial do CSV

O dicionário harmonizado das variáveis do Pima e do NHANES está em
[`../dicionario_variaveis_healthai.csv`](../dicionario_variaveis_healthai.csv).
Ele deve orientar a criação das tabelas processadas sem apagar diferenças entre
protocolos de medição.

O baseline adota o esquema conhecido do conjunto Pima Indians Diabetes:

| Coluna | Descrição | Tipo |
|---|---|---|
| `Pregnancies` | Número de gestações | inteiro |
| `Glicose` | Concentração de glicose | numérico |
| `BloodPressure` | Pressão arterial diastólica | numérico |
| `SkinThickness` | Espessura da prega cutânea | numérico |
| `Insulin` | Insulina sérica | numérico |
| `BMI` | Índice de massa corporal | numérico |
| `DiabetesPedigreeFunction` | Histórico familiar calculado | numérico |
| `Age` | Idade em anos | inteiro |
| `Outcome` | Classe-alvo: 0 ou 1 | inteiro |

Se outra base for escolhida, atualize este dicionário e
`configs/models.yaml`. Registre também fonte, versão, licença, critérios de
inclusão, método de anonimização e data de acesso.
