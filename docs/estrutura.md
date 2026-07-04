# Estrutura e responsabilidades

```text
dados brutos -> validação -> divisão treino/teste -> tuning e CV no treino
            -> limiar F2 -> seleção -> teste -> modelo + métricas + figuras
```

- `configs/`: mantém parâmetros fora do código para repetir experimentos.
- `data/`: separa a fonte original das transformações e evita sobrescrita.
- `src/healthai/data.py`: leitura e validação do esquema.
- `src/healthai/features.py`: pré-processamento e fábrica dos classificadores.
- `src/healthai/train.py`: divisão, comparação, avaliação e persistência.
- `src/healthai/predict.py`: aplicação do modelo salvo a novos registros.
- `backend/`: autenticação, banco de usuários e serviço FastAPI dos modelos.
- `frontend/`: formulário React, resultado acadêmico e comparação de métricas.
- `tests/`: protege regras de validação e transformações.
- `reports/`: guarda resultados usados no texto do TCC.

Cada artefato salvo contém pré-processamento e classificador no mesmo pipeline.
Isso evita aplicar transformações diferentes no treino e na inferência e reduz
o risco de vazamento de dados.

O banco da aplicação é separado dos CSVs analíticos. Ele guarda hashes de
senha Argon2, hashes dos tokens de sessão, aceite versionado do aviso de
privacidade e resultados vinculados apenas a identificadores pseudonimizados.
As variáveis clínicas usadas na inferência não são persistidas. Resultados
expirados são removidos conforme a política de retenção configurada.
