# Escalabilidade de leitura

## Estado implementado

- os índices seguem os filtros, ordenações, rotinas de retenção e chaves
  estrangeiras efetivamente usados pela API;
- cada processo reutiliza conexões por meio de um pool limitado, com validação
  antes do uso e reciclagem periódica;
- uma ou mais réplicas PostgreSQL podem receber as consultas de histórico de
  resultados, em distribuição round-robin;
- sessões destinadas às réplicas rejeitam `INSERT`, `UPDATE`, `DELETE`, flush e
  commit; em produção, essa proteção deve ser reforçada com um usuário do banco
  que possua somente `SELECT`;
- migrações, autenticação, renovação de sessão, consentimentos, predições,
  retenção e exclusões sempre usam o banco primário;
- se uma réplica não aceitar a conexão, a API volta ao primário por padrão e
  registra o evento sem expor credenciais.

O deploy atual continua usando SQLite e, portanto, não ativa réplicas. SQLite
tem pool e modo WAL, mas não oferece replicação nativa nem é adequado para
escalar a API em vários servidores. Para ativar réplicas, primeiro migre o
banco primário para PostgreSQL e obtenha as URLs de leitura no provedor do
banco.

## Configuração do pool

```dotenv
HEALTHAI_DB_POOL_SIZE=5
HEALTHAI_DB_MAX_OVERFLOW=10
HEALTHAI_DB_POOL_TIMEOUT_SECONDS=30
HEALTHAI_DB_POOL_RECYCLE_SECONDS=1800
```

`POOL_SIZE` é a quantidade de conexões persistentes por engine e por processo.
`MAX_OVERFLOW` é a folga temporária; quando ambos se esgotam, uma requisição
espera até `POOL_TIMEOUT_SECONDS`. `pool_pre_ping` elimina conexões quebradas e
o modo LIFO permite que conexões excedentes permaneçam ociosas e sejam
recicladas.

O teto teórico deve caber em `max_connections` do PostgreSQL, reservando espaço
para administração e tarefas do provedor:

```text
processos_da_API × (1 + quantidade_de_réplicas) × (pool_size + max_overflow)
```

Cada réplica tem seu próprio limite. O valor é um teto, não uma meta; ajuste-o
com métricas de latência, conexões ocupadas, timeout do pool e CPU/IO do banco.

## Configuração de read replicas

Exemplo ilustrativo; os segredos devem existir apenas no ambiente do servidor:

```dotenv
HEALTHAI_DATABASE_URL=postgresql+psycopg://healthai_writer:SEGREDO@primary.example/healthai
HEALTHAI_READ_DATABASE_URLS=postgresql+psycopg://healthai_reader:SEGREDO@replica-a.example/healthai,postgresql+psycopg://healthai_reader:SEGREDO@replica-b.example/healthai
HEALTHAI_READ_REPLICA_FALLBACK=true
```

O primário e as réplicas precisam usar o mesmo SGBD. A API aplica Alembic
somente no primário; a infraestrutura PostgreSQL replica as mudanças e os dados.
Não configure apenas uma segunda URL apontando para o mesmo servidor: isso não
distribui trabalho.

As réplicas são eventualmente consistentes. Logo após criar ou excluir uma
avaliação, `GET /results` pode refletir o estado anterior por alguns
milissegundos ou segundos. A resposta do próprio `POST /predict/*` vem do
primário e é consistente. Autenticação e operações clínicas que escrevem não
dependem da réplica. Desative o fallback somente se for preferível retornar erro
em vez de aumentar carga no primário durante uma falha:

```dotenv
HEALTHAI_READ_REPLICA_FALLBACK=false
```

## Índices cobertos

- `prediction_results (user_id, created_at, id)` cobre paginação e ordenação do
  histórico; `created_at` isolado cobre a retenção global;
- `crm_review_events (user_id, created_at, id)` cobre a trilha de auditoria;
- `crm_verification_challenges (user_id, created_at)` cobre o desafio atual e
  `expires_at` cobre a limpeza periódica;
- `users (crm_status, created_at)` e `users (created_at)` cobrem filtros e
  rotinas operacionais;
- índices das chaves estrangeiras aceleram exclusões em cascata e `SET NULL`;
- índices por `(user_id, created_at)` cobrem a busca do token mais recente;
- hashes de sessão, verificação e recuperação já possuem índices únicos.

A busca parcial de identificador usa `ILIKE '%trecho%'`; um índice B-tree não
acelera esse padrão. Se as métricas mostrarem esse hotspot após a migração para
PostgreSQL, avalie um índice GIN com `pg_trgm` antes de acrescentá-lo, pois ele
aumenta custo de escrita e armazenamento.

## Cache e CDN

Não foi adicionado Redis aos resultados clínicos: são dados personalizados,
mudam após cada predição/exclusão e ainda não há evidência de um hotspot que
justifique invalidação e uma nova cópia de dado sensível. Um cache deve entrar
somente após medição, com chave por usuário, TTL curto e invalidação explícita.

Os assets versionados do frontend já recebem
`Cache-Control: public, max-age=31536000, immutable` no Caddy. Uma CDN pode ser
colocada à frente desses assets quando distribuição geográfica ou volume
justificar; respostas de `/api/*` não devem ser armazenadas por uma CDN.

## Validação operacional

Antes e depois de cada ajuste, acompanhe p50/p95/p99 das rotas e consultas,
taxa de erro, espera no pool, conexões ativas, CPU, memória, IO, cache hit do
PostgreSQL e atraso de replicação. Faça teste de carga com dados sintéticos e
um perfil próximo ao real. Réplica e cache não corrigem consulta sem índice nem
pool superdimensionado.
