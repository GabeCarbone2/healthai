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
- `src/healthai/evaluate.py`: métricas, calibração, intervalos, subgrupos,
  explicabilidade por permutação e resumo de disparidades.
- `src/healthai/predict.py`: aplicação do modelo salvo a novos registros.
- `backend/`: autenticação, banco de usuários e serviço FastAPI dos modelos.
- `frontend/`: formulário React, resultado acadêmico e comparação de métricas.
- `tests/`: protege regras de validação e transformações.
- `reports/`: guarda resultados usados no texto do TCC.

Cada artefato salvo contém pré-processamento e classificador no mesmo pipeline.
Isso evita aplicar transformações diferentes no treino e na inferência e reduz
o risco de vazamento de dados.

Os relatórios em `reports/` incluem a comparação dos modelos, figuras de
calibração, figuras de importância por permutação e o estado da validação
externa. A discussão interpretativa fica em `docs/modelo.md`.

O banco da aplicação é separado dos CSVs analíticos. Ele guarda hashes de
senha Argon2, hashes dos tokens de sessão, aceite versionado do aviso,
desafios efêmeros de verificação, hashes da evidência assinada, auditoria
imutável das aprovações de CRM e resultados vinculados apenas a
identificadores pseudonimizados. Cada resultado registra versão do modelo e
completude, mas não os valores clínicos usados na inferência. Registros
expirados são removidos periodicamente conforme a retenção configurada.

`backend/crm_verification.py` gera o desafio PDF e valida a assinatura PAdES,
a cadeia ICP-Brasil, revogação e os OIDs de CRM/UF. O arquivo assinado é
processado apenas em memória. `backend/auth.py` expõe criação, download, estado
e envio do desafio, consumindo-o de forma atômica antes de aprovar a conta.
