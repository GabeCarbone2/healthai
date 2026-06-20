# Roteiro metodológico do TCC

## Pergunta de pesquisa

Em que medida algoritmos de classificação supervisionada conseguem identificar
pacientes com maior risco de diabetes no conjunto de dados selecionado?

## Etapas

1. Revisão bibliográfica e definição das variáveis.
2. Avaliação da qualidade, proveniência e representatividade dos dados.
3. Análise exploratória e tratamento de valores ausentes ou inválidos.
4. Separação estratificada entre treino e teste.
5. Baseline com regressão logística.
6. Comparação com árvores, Random Forest e gradient boosting por validação
   cruzada, mantendo o conjunto de teste isolado.
7. Avaliação com matriz de confusão, precisão, recall, F1 e ROC-AUC.
8. Análise de explicabilidade, calibração, vieses e limitações.

## Cuidados importantes

- evitar usar informação do conjunto de teste durante seleção do modelo;
- não interpretar associação estatística como causalidade;
- justificar o limiar de decisão conforme o custo de falsos negativos;
- verificar desempenho por grupos demográficos quando os dados permitirem;
- documentar consentimento, anonimização, licença e conformidade com a LGPD;
- apresentar o modelo como apoio acadêmico, nunca como diagnóstico autônomo.

