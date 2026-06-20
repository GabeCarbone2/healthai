# Estrutura e responsabilidades

```text
dados brutos -> validação -> divisão treino/teste -> pipeline de pré-processamento
            -> treinamento -> avaliação -> modelo + métricas + figuras
```

- `configs/`: mantém parâmetros fora do código para repetir experimentos.
- `data/`: separa a fonte original das transformações e evita sobrescrita.
- `src/healthai/data.py`: leitura e validação do esquema.
- `src/healthai/features.py`: construção do pipeline de pré-processamento.
- `src/healthai/train.py`: divisão, treino, avaliação e persistência.
- `src/healthai/predict.py`: aplicação do modelo salvo a novos registros.
- `tests/`: protege regras de validação e transformações.
- `reports/`: guarda resultados usados no texto do TCC.

O artefato salvo contém pré-processamento e classificador no mesmo pipeline.
Isso evita aplicar transformações diferentes no treino e na inferência e reduz
o risco de vazamento de dados.

