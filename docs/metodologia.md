# Roteiro metodológico do TCC

## Pergunta de pesquisa

Em que medida algoritmos de classificação supervisionada conseguem identificar
pacientes com maior risco de diabetes no conjunto de dados selecionado?

## Etapas

1. Revisão bibliográfica e definição das variáveis.
2. Avaliação da qualidade, proveniência e representatividade dos dados.
3. Análise exploratória e tratamento de valores ausentes ou inválidos.
4. Separação estratificada entre treino e teste.
5. Treinamento de Regressão Logística como baseline interpretável.
6. Ajuste de Regressão Logística, Random Forest e SVM com busca aleatória e
   validação cruzada, mantendo o conjunto de teste isolado.
7. Definição de limiar por F2 usando probabilidades out-of-fold do treino.
8. Avaliação no teste isolado com matriz de confusão, precisão, recall, F1,
   ROC-AUC, Brier score e curva de calibração.
9. Comparação posterior com métodos de Gradient Boosting.
10. Intervalos de confiança por bootstrap e análise por sexo/faixa etária,
    com explicitação de amostras pequenas.
11. Explicabilidade por importância de permutação no teste isolado.
12. Resumo de disparidades por subgrupo e documentação de validação externa.
13. Seção explícita de limitações.

O SVM usa calibração sigmoide explícita sobre o `SVC`, equivalente à geração
de probabilidades adotada nos notebooks e compatível com as versões atuais do
scikit-learn.

## Seleção dos modelos

Primeiro é reservada uma amostra estratificada de 20% para o teste. Nos 80%
restantes, cada candidato passa por oito combinações aleatórias de
hiperparâmetros, avaliadas com validação cruzada estratificada de cinco folds,
embaralhamento e semente 42. O maior F1 médio define o modelo:

- Pima: Random Forest, F1 médio de 0,6834 (desvio de 0,0282);
- NHANES: SVM, F1 médio de 0,7152 (desvio de 0,0143).

Para cada candidato ajustado, probabilidades out-of-fold do treino determinam
o limiar que maximiza F2, atribuindo peso maior ao recall. O limiar escolhido
foi 0,21 no Pima e 0,13 no NHANES.

Depois da seleção, o teste é usado uma única vez para estimar o desempenho
final. A Random Forest obteve recall de 0,8889, F1 de 0,6443 e ROC-AUC de
0,8250 no Pima. O SVM obteve recall de 0,8011, F1 de 0,6039 e ROC-AUC de
0,9005 no NHANES. Os limiares baixos aumentam a sensibilidade, mas também os
falsos positivos; essa troca deve ser discutida como decisão experimental, não
como recomendação clínica.

Os modelos são treinados separadamente porque as bases têm populações,
variáveis disponíveis e definições de desfecho diferentes. No Pima são usadas
as oito variáveis do conjunto clássico. No NHANES são usados sexo, idade, IMC,
pressões sistólica e diastólica, hemoglobina glicada e glicose. O experimento
NHANES inclui somente adultos e trata pressão diastólica abaixo de 30 mmHg como
ausente. Sexo é codificado como uma única variável binária, reproduzindo as
regras do notebook.

## Calibração, incerteza e subgrupos

A avaliação probabilística usa o Brier score (menor é melhor), uma curva de
calibração com dez grupos de tamanho semelhante e o erro esperado de calibração
(ECE). O Brier score não deve ser interpretado isoladamente como calibração,
pois também combina resolução/discriminação e a incerteza do desfecho. Os
pontos completos das curvas ficam em `reports/model_comparison.json`, e as
figuras em `reports/figures/`.

Para cada modelo, intervalos de confiança de 95% são estimados por 2.000
reamostragens bootstrap pareadas das observações do teste. Os intervalos
quantificam a variabilidade amostral condicional ao modelo já treinado; eles não
incorporam a incerteza de repetir treinamento, ajuste de hiperparâmetros ou
coleta em outra população.

O modelo Pima é auditado por faixa etária. O NHANES é auditado por sexo e faixa
etária. Cada grupo registra tamanho, número de positivos e prevalência.
Estimativas com menos de 20 observações não são calculadas; grupos com menos de
dez eventos em qualquer classe são marcados como limitados, mesmo quando a
métrica descritiva é exibida.

Além das métricas por subgrupo, o relatório calcula um resumo de disparidades
absolutas para recall, precisão, taxa de falso positivo, ROC-AUC e Brier score.
Esse resumo facilita identificar onde há maior diferença observada, mas deve
ser lido como auditoria descritiva no teste, não como prova causal de viés.

Nos modelos selecionados, os resultados globais foram:

| Base | Modelo | Brier | ECE | Recall (IC 95%) | ROC-AUC (IC 95%) |
|---|---|---:|---:|---:|---:|
| Pima | Random Forest | 0,1649 | 0,0850 | 0,8889 (0,8036–0,9667) | 0,8250 (0,7535–0,8859) |
| NHANES | SVM calibrado | 0,0733 | 0,0197 | 0,8011 (0,7378–0,8588) | 0,9005 (0,8729–0,9258) |

No NHANES, o recall foi 0,8511 entre homens (n=564) e 0,7439 entre mulheres
(n=572). Por idade, foi 0,2500 em 18–39 anos, 0,7708 em 40–59 e 0,8500 em 60+.
O primeiro grupo possuía somente oito casos positivos, portanto a estimativa
foi marcada como limitada e apresentou IC 95% amplo (0,0000–0,6000). Esses
resultados são sinais para investigação de representatividade e definição do
desfecho, não evidência causal nem prova de equidade.

No Pima, o recall foi 0,8333 em 21–39 anos e 1,0000 em 40–59. O grupo 60+
continha apenas seis pessoas e não recebeu estimativa. O IC degenerado do
recall em 40–59 (1,0000–1,0000) reflete que todos os positivos desse teste
foram detectados pelo modelo fixo; não significa desempenho perfeito na
população.

Referências metodológicas centrais para essa seção incluem Brier (1950),
*Verification of Forecasts Expressed in Terms of Probability*; Niculescu-Mizil
e Caruana (2005), *Predicting Good Probabilities with Supervised Learning*; e
Efron e Tibshirani (1993), *An Introduction to the Bootstrap*.

## Explicabilidade e validação externa

Para o modelo selecionado de cada base, o pipeline calcula importância por
permutação no teste isolado, usando ROC-AUC como métrica. As figuras ficam em
`reports/figures/pima_feature_importance.png` e
`reports/figures/nhanes_feature_importance.png`. As importâncias indicam quanto
o desempenho cai quando uma variável é embaralhada; elas não indicam efeito
causal nem relevância clínica individual.

O relatório também registra explicitamente o estado da validação externa.
Neste estágio, ela está marcada como não realizada. Pima e NHANES são tratados
como experimentos separados porque não compartilham o mesmo desenho, população,
conjunto de variáveis e definição de desfecho. Portanto, testar um modelo em
outra fonte sem compatibilização não seria validação externa adequada.

A validação externa planejada deve congelar o artefato, variáveis,
pré-processamento, hiperparâmetros e limiar, e então aplicar o modelo a uma
coorte independente compatível, reportando métricas, calibração, intervalos de
confiança e subgrupos sem reajuste.

Um resumo pronto para o TCC está em [`docs/modelo.md`](modelo.md).

## Cuidados importantes

- evitar usar informação do conjunto de teste durante seleção do modelo;
- não interpretar associação estatística como causalidade;
- justificar o limiar de decisão conforme o custo de falsos negativos;
- verificar desempenho por grupos demográficos quando os dados permitirem;
- interpretar intervalos e subgrupos junto aos respectivos tamanhos e número
  de eventos;
- documentar consentimento, anonimização, licença e conformidade com a LGPD;
- apresentar o modelo como apoio acadêmico, nunca como diagnóstico autônomo.
