# Notebooks

Numere os notebooks na ordem de execução:

1. `01_analise_exploratoria.ipynb`
2. `02_pre_processamento.ipynb`
3. `03_comparacao_modelos.ipynb`
4. `04_interpretabilidade.ipynb`

Notebooks servem para exploração e comunicação. Transformações definitivas
devem ser movidas para `src/healthai` para que possam ser testadas e repetidas.

Os testes iniciais dos notebooks de Pima e NHANES orientaram os candidatos e
parâmetros de `configs/models.yaml`. A seleção reproduzível definitiva é feita
por `src/healthai/train.py`, com validação cruzada restrita ao treino.
