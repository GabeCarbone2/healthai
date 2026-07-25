# Auditoria e melhoria do pipeline de machine learning

Data da revisão: 25 de julho de 2026.

## 1. Problemas encontrados e risco metodológico

| Problema anterior | Risco | Decisão aplicada |
|---|---|---|
| Limpeza repetida no treino, lote e API | A mesma pessoa poderia receber probabilidades diferentes conforme a interface | Criado um único contrato em `input_validation.py` e uma única inferência em `inference.py` |
| Sexo do NHANES mapeado manualmente para número | Categoria nova virava ausente silenciosamente e a codificação ficava fora do pipeline | `sex` passou a ser categórica, validada e codificada por `OneHotEncoder` dentro do pipeline |
| Busca e avaliação de CV reutilizavam a configuração já escolhida | Estimativa otimista da seleção de hiperparâmetros | Implementada CV aninhada estratificada, 5 dobras externas e 4 internas |
| Modelo escolhido por F1, mas limiar escolhido por F2 | Critérios de seleção inconsistentes | Candidatos agora são comparados por average precision OOF; o limiar é uma segunda decisão, por F-beta OOF |
| Faixas observadas eram tratadas como limites absolutos | Bloqueio indevido de valores plausíveis e extrapolação silenciosa | Limites físicos bloqueiam; faixas observadas no treino apenas geram aviso |
| Artefato sem contrato versionado | Incompatibilidade ou corrupção poderia aparecer apenas durante a predição | Adotado schema `2.0`, validação no carregamento e migração conservadora de artefatos v1 |
| Bootstrap simples | Reamostras podiam perder uma classe, principalmente em subgrupos | Bootstrap estratificado pelo desfecho, com contagem de reamostras válidas/descartadas |
| Métricas limitadas | Desempenho incompleto em problema desbalanceado e clínico | Incluídas AP/PR-AUC, acurácia balanceada, VPP, VPN, sensibilidade, especificidade, LR+/LR− e prevalência |
| Ausência de intercepto e inclinação de calibração | Diagrama e Brier isolados não descreviam bem viés e escala das probabilidades | Incluída regressão logística de calibração sobre o logit das probabilidades |
| Escrita direta de modelos e JSON | Interrupção poderia deixar arquivo parcial | Joblib e JSON passam por arquivo temporário, `fsync` e substituição atômica |

## 2. Auditoria de `diabetes_outcome`

### Pima

O script `scripts/download_datasets.py` lê a classe original do OpenML 37 e
mapeia `tested_negative` para 0 e `tested_positive` para 1. O alvo harmonizado
é copiado para `diabetes_outcome`, com a definição `pima_dataset_outcome`.
Nenhuma feature do modelo é usada para reconstruir esse alvo.

### NHANES

O alvo é criado exclusivamente por:

```python
merged["DIQ010"].map({1.0: 1, 2.0: 0})
```

Logo, 1 significa que o participante informou já ter recebido diagnóstico de
diabetes por médico ou profissional de saúde; 0 significa resposta “não”.
Respostas limítrofes, recusadas, desconhecidas ou ausentes não entram como
classe. Medicação, HbA1c e glicose não participam da regra do alvo.

Não foi alterada silenciosamente a semântica do desfecho. O relatório e os
artefatos registram definição e uso pretendido.

## 3. Vazamento e circularidade no NHANES

Não existe vazamento mecânico direto: `hba1c_percent` e `glucose_mg_dl` não
constroem `DIQ010`. Existe, porém, forte sobreposição clínica e temporal.
Exames concorrentes estão associados ao diagnóstico prévio que forma o alvo e
podem refletir tanto a condição quanto tratamento iniciado após o diagnóstico.

Por isso, o modelo NHANES é um classificador transversal de diabetes
previamente diagnosticado na amostra analítica. Ele não deve ser apresentado
como previsão de incidência futura, diagnóstico de diabetes não reconhecido ou
estimativa causal. Um modelo de risco futuro exigiria coorte longitudinal,
tempo zero, horizonte de previsão e exclusão de variáveis posteriores ao
início do acompanhamento.

## 4. Zeros do Pima

`glucose_mg_dl`, `diastolic_bp_mmhg`, `skin_thickness_mm`,
`serum_insulin_muu_ml` e `bmi_kg_m2` usam zero como ausência no conjunto
clássico. Esses zeros são convertidos em ausentes, registrados como imputados e
tratados pelo `SimpleImputer` ajustado apenas na parcela de treino.
`pregnancies=0` permanece válido.

As mesmas regras estão no YAML, no artefato e em treino, lote e API.

## 5. Validação aninhada, seleção e limiar

O teste é separado primeiro, com estratificação e semente fixa. Para cada
candidato:

1. cada dobra externa isola sua validação;
2. a busca aleatória ocorre apenas nas dobras internas do desenvolvimento;
3. a melhor configuração prevê a dobra externa;
4. todas as previsões externas formam o vetor OOF;
5. os candidatos são comparados por average precision OOF;
6. o limiar maximiza F-beta, com beta 2, apenas nesse vetor OOF;
7. uma busca final ocorre na partição completa de treino;
8. o teste é consultado uma única vez para a avaliação final.

O relatório guarda scores e tamanhos das dobras, parâmetros externos, média,
desvio, mínimo, máximo, probabilidades/índices OOF, melhor configuração final e
escopo de cada etapa. Nenhuma restrição clínica de recall foi inventada.

## 6. Resultados finais no teste isolado

| Base | Selecionado | Limiar | AP/PR-AUC | ROC-AUC | Recall | Especificidade | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pima | SVM calibrado internamente | 0,14 | 0,6903 | 0,8124 | 0,9444 | 0,4900 | 0,1744 |
| NHANES | Random Forest | 0,38 | 0,7098 | 0,9173 | 0,8352 | 0,8375 | 0,0918 |

Intervalos bootstrap de 95%:

- Pima: recall 0,8704–1,0000; especificidade 0,3900–0,5900;
  ROC-AUC 0,7430–0,8743; AP 0,5919–0,7889.
- NHANES: recall 0,7784–0,8864; especificidade 0,8135–0,8604;
  ROC-AUC 0,8943–0,9379; AP 0,6441–0,7860.

Os limiares priorizam sensibilidade e não possuem validação de utilidade
clínica.

## 7. Calibração

Além do Brier score e da curva em bins quantis, são reportados ECE, intercepto
e inclinação:

- Pima: ECE 0,1215, intercepto −0,1043, inclinação 0,7753;
- NHANES: ECE 0,1088, intercepto −1,2686, inclinação 0,9656.

Calibração adicional é configurável (`sigmoid` ou `isotonic`) e ocorre dentro
das dobras quando habilitada. Ela permanece desabilitada no experimento final:
não foi escolhido um calibrador consultando o teste, e a isotônica é recusada
abaixo do tamanho mínimo configurado.

## 8. Bootstrap e subgrupos

O bootstrap reamostra positivos e negativos separadamente, preserva pares de
classe/predição/probabilidade e informa total válido e descartado. Ele cobre
métricas dependentes e independentes do limiar.

Cada subgrupo informa tamanho, eventos, não eventos, prevalência, ausências,
status, avisos e intervalos. Grupos pequenos não são escondidos. Gaps recebem
bootstrap estratificado por grupo e desfecho quando há pelo menos dois grupos
comparáveis.

Achados descritivos principais:

- Pima: `60+` tem somente 6 pessoas e 1 evento, portanto não é estimado;
- NHANES por sexo: grupos têm tamanhos semelhantes e recall próximo;
- NHANES de 18–39 anos tem apenas 8 eventos; o recall 0,25 é marcado como
  limitado e não deve sustentar conclusão forte.

Essas diferenças não provam causalidade, discriminação ou equidade
populacional.

## 9. Entradas, lote e API

`prepare_and_validate_input` devolve dados preparados, elegibilidade, erros,
avisos, variáveis ausentes/imputadas, completude, extrapolação e motivos de
exclusão por linha.

- Categoria desconhecida, valor infinito, limite físico, incoerência de
  pressão, população inelegível e campo obrigatório bloqueiam.
- Ausência opcional e faixa fora do treino geram aviso.
- O mínimo de completude é configurável e está `null` nos experimentos atuais.
- O lote grava `prediction_status`, erros, avisos, ausências, imputações,
  limiar e versão; `--fail-on-invalid` torna a execução não zero após salvar o
  diagnóstico.
- A API retorna 422 detalhado para entrada inválida, 503 para modelo ausente ou
  incompatível e não registra valores clínicos nos logs.

A explicação individual passou a declarar explicitamente
`local_sensitivity_to_training_reference`. Ela informa probabilidade original,
probabilidade de referência e efeito absoluto, mantendo os campos legados.
Não é aditiva nem causal.

## 10. Artefato e rastreabilidade

O schema `2.0` contém pipeline, ordem/tipo das features, contrato de validação,
filtros, definição do alvo, fonte, modelo, versão, CV, limiar, faixas observadas
no treino, validação externa, decisão sobre pesos e metadados de treinamento.

Os metadados incluem data UTC, Python e bibliotecas, SHA-256 dos dados,
configuração e código, commit Git, tamanhos, prevalências, regras e integridade
da separação. A versão muda com dados, configuração, código, hiperparâmetros,
limiar e schema. Artefatos v1 recebem apenas padrões seguros; incompatibilidades
graves são recusadas.

## 11. Pesos do NHANES, DCA e validação externa

Os campos `fasting_sample_weight`, `survey_stratum` e `survey_psu` existem na
base. Pesos não foram aplicados porque o pipeline atual não implementa ajuste e
variância sob desenho amostral complexo. Assim, os resultados descrevem a
amostra analítica e não são estimativas representativas dos Estados Unidos.

Decision Curve Analysis permanece `not_performed`: ainda faltam
probabilidades-limiar clinicamente justificadas. Uma implementação técnica sem
essa decisão poderia produzir aparência indevida de utilidade clínica.

Validação externa permanece `not_performed`. Teste interno, CV e outra base com
variáveis/desfecho diferentes não são validação externa. O protocolo futuro
deve congelar artefato e limiar e usar coorte independente com população,
variáveis, tempo e definição de desfecho compatíveis.

## 12. Arquivos alterados

- configuração: `configs/models.yaml`, `pyproject.toml`;
- núcleo ML: `config.py`, `input_validation.py`, `features.py`, `train.py`,
  `evaluate.py`, `inference.py`, `predict.py`, `artifacts.py`;
- API: `backend/model_service.py`, `backend/schemas.py`, `backend/app.py`;
- testes: `test_config.py`, `test_artifacts.py`, `test_input_validation.py` e
  extensões dos testes de treino, avaliação e serviço;
- artefatos/relatórios: modelos selecionados, comparação, qualidade dos dados,
  calibração e importância;
- documentação: este relatório, `README.md`, `docs/modelo.md` e
  `data/README.md`.

## 13. Testes e comandos

Comandos principais:

```bash
python -m ruff check src/healthai backend tests
python -m pytest -q
python -m healthai.train --config configs/models.yaml
npm --prefix frontend test
```

Os testes incluem zeros e gestações do Pima, categorias, campos obrigatórios,
limites, aplicabilidade, completude, entrada vazia/duplicada/infinita, alvo
binário, CV/OOF, separação treino-teste, versão, schema, interrupção de escrita,
bootstrap, classe única, equivalência API/lote, determinismo e códigos HTTP.

Resultado final:

- backend/ML: 89 testes aprovados;
- frontend: 25 testes aprovados em 6 arquivos;
- Ruff: sem erro;
- build TypeScript/Vite: concluído;
- `git diff --check`: sem erro;
- equivalência real API/lote: probabilidade, classe, limiar, versão,
  completude e avisos idênticos dentro de `rtol=1e-10`, `atol=1e-12`.

## 14. Limitações e decisões clínicas pendentes

- Desfechos são transversais e diferentes entre as bases.
- Não há coorte longitudinal nem validação externa.
- NHANES contém circularidade clínica/temporal, embora não vazamento mecânico.
- O Pima tem população histórica e específica, com muitos valores ausentes.
- Imputação não recupera informação realmente observada.
- Faixas fora do treino são avisadas, mas o modelo ainda extrapola.
- Não há pesos/desenho amostral no NHANES.
- Não há DCA, estudo prospectivo, revisão de custo de erro ou limiar clínico.
- Importância por permutação e sensibilidade local não são causais; correlação
  entre features pode mascarar ou dividir importância.
- Métricas de subgrupos pequenos têm alta incerteza.

Decisões que dependem de revisão clínica: população-alvo, finalidade
(triagem/diagnóstico/prognóstico), horizonte temporal, custo de falso
positivo/negativo, limiar aceitável, variáveis disponíveis no momento de uso e
faixas físicas por unidade/protocolo.

## 15. Atualizações necessárias no artigo

O texto do TCC deve:

1. substituir “predição de risco futuro” por classificação do desfecho
   observado, salvo se o desenho do estudo for alterado;
2. descrever exatamente `DIQ010` e a classe original do Pima;
3. explicitar circularidade dos exames concorrentes no NHANES;
4. trocar CV simples por CV aninhada e F1 por AP na seleção;
5. registrar a otimização F-beta do limiar somente em OOF;
6. atualizar tabela de modelos, métricas, ICs e calibração;
7. descrever zeros como ausentes e imputação ajustada no treino;
8. declarar pesos do NHANES não aplicados e proibir inferência populacional;
9. manter validação externa e DCA como não realizadas;
10. incluir schema/versionamento, contrato de entrada e testes como medidas de
    reprodutibilidade, sem transformá-las em evidência clínica.
