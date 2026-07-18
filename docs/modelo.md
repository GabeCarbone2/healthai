# Qualidade, explicabilidade e limites dos modelos

Este documento complementa a metodologia com quatro pontos exigidos para uma
avaliação responsável: explicabilidade, validação externa, análise de viés e
limitações.

## Uso pretendido

Os modelos são classificadores acadêmicos dos desfechos registrados nas bases,
não calculadoras clinicamente validadas de risco futuro:

- no Pima, o alvo é a classe `tested_positive`/`tested_negative` do conjunto
  clássico, restrito à população feminina de herança indígena Pima;
- no NHANES, o alvo é `DIQ010`, autorrelato de diagnóstico médico prévio de
  diabetes.

Consequentemente, o resultado não identifica de forma validada diabetes não
diagnosticado e não estima incidência futura. Esses usos exigiriam outro desenho
de desfecho, coorte adequada e validação externa. A interface usa a expressão
“probabilidade estimada da classe do estudo” para preservar essa distinção.

## Explicabilidade

O treinamento calcula importância por permutação no conjunto de teste isolado
para o modelo selecionado de cada base. A métrica usada é ROC-AUC, com 20
repetições e semente 42. O resultado fica em `reports/model_comparison.json` e
as figuras ficam em:

- `reports/figures/pima_feature_importance.png`;
- `reports/figures/nhanes_feature_importance.png`.

Nos artefatos atuais, as variáveis mais sensíveis foram:

| Base | Modelo | Principais variáveis por permutação |
|---|---|---|
| Pima | Random Forest | glicose, IMC, idade, insulina sérica, gestações |
| NHANES | SVM calibrado | hemoglobina glicada, idade, glicose, IMC, pressão sistólica |

Essas importâncias indicam queda de desempenho quando uma variável é
embaralhada no teste. Elas não provam causalidade, não substituem análise
clínica e podem mudar quando a população, o limiar ou o conjunto de variáveis
muda.

## Validação Externa

Ainda não há validação externa verdadeira. O projeto usa teste isolado da
mesma fonte de cada experimento:

- Pima: treino e teste vêm do conjunto Pima;
- NHANES: treino e teste vêm da onda NHANES 2017-2018.

O NHANES não é validação externa direta do Pima porque as bases têm população,
variáveis disponíveis e definição de desfecho diferentes. Uma validação externa
adequada deve congelar o artefato, as variáveis, o pré-processamento, os
hiperparâmetros e o limiar; aplicar o modelo a uma coorte independente
compatível; e reportar métricas, calibração, intervalos de confiança e
subgrupos sem reajustar o modelo nessa coorte.

## Análise De Viés

O relatório inclui desempenho por subgrupos e um resumo de disparidades
absolutas. As métricas auditadas incluem recall, precisão, taxa de falso
positivo, ROC-AUC e Brier score.

Nos modelos selecionados atuais:

- Pima por idade: o recall foi maior em 40-59 do que em 21-39, com gap de
  0,1667. O grupo 60+ tem amostra insuficiente e não deve ser interpretado.
- NHANES por sexo: o recall foi maior entre homens do que entre mulheres, com
  gap de 0,1072. A taxa de falso positivo também foi maior entre homens, com
  gap de 0,0482.
- NHANES por idade: o maior gap de recall foi 0,6000 entre 18-39 e 60+, mas o
  grupo 18-39 tem poucos eventos positivos e o relatório marca a estimativa
  como limitada.

Essas diferenças são sinais descritivos no teste. Elas não demonstram
discriminação causal, nem garantem equidade populacional. Para uso fora do TCC,
seria necessário ampliar a auditoria com dados externos, análise de
representatividade e revisão clínica dos custos de erro por grupo.

## Limitações

- Finalidade acadêmica: o sistema não faz diagnóstico e não substitui avaliação
  médica.
- Dados secundários: Pima e NHANES possuem vieses próprios de coleta,
  população, época e definição do desfecho.
- Generalização limitada: o desempenho foi estimado em teste isolado interno,
  sem coorte externa independente.
- Limiar experimental: os limiares F2 priorizam recall e aumentam falsos
  positivos; eles não foram definidos por estudo clínico de custo-benefício.
- Subgrupos pequenos: algumas faixas têm poucos eventos, gerando incerteza alta
  ou impedindo estimativa.
- Explicabilidade não causal: importância por permutação mostra associação com
  desempenho, não efeito clínico causal.
- Probabilidades imperfeitas: calibração e Brier score ajudam a avaliar risco,
  mas não eliminam erro de previsão individual.
- Entrada manual: erros de digitação, unidade ou contexto clínico ausente podem
  alterar a previsão.
- Privacidade: identificadores diretos de pacientes não devem ser inseridos; o
  código `PAC-...` continua sendo pseudonimização, não anonimização plena.
