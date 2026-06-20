# Dados

Os arquivos de pacientes não devem ser enviados ao Git. A pasta mantém apenas
este dicionário e marcadores vazios.

## Diretórios

- `raw/`: cópia imutável dos dados obtidos na fonte;
- `interim/`: resultados intermediários de limpeza;
- `processed/`: dados finais usados pelos modelos;
- `external/`: documentação ou dados auxiliares públicos.

## Esquema inicial do CSV

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
`configs/baseline.yaml`. Registre também fonte, versão, licença, critérios de
inclusão, método de anonimização e data de acesso.

