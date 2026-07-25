# Publicação no VPS da Hostinger

O ambiente de produção usa dois contêineres:

- `web`: compila o React, publica os arquivos estáticos e obtém HTTPS
  automaticamente com Caddy;
- `api`: executa FastAPI, aplica as migrações Alembic na inicialização e mantém
  o SQLite em um volume persistente.

Esse formato é adequado ao volume inicial, mas não oferece read replicas. A API
já aceita PostgreSQL com pools e réplicas externas; a arquitetura, as variáveis
e os trade-offs de consistência estão em
[`escalabilidade.md`](escalabilidade.md). Não configure uma réplica SQLite nem
duas URLs para o mesmo banco.

## 1. Preparar o VPS

Selecione o template **Ubuntu 24.04 com Docker**, que já inclui Docker Engine e
Docker Compose. Em uma instalação Ubuntu limpa, instale o Docker pelo
repositório oficial.
No firewall da Hostinger, permita as portas `22`, `80` e `443`; restrinja a
porta `22` ao seu IP sempre que possível.

Configure uma chave SSH para administração. Não use senha de root em comandos,
arquivos do projeto ou mensagens.

## 2. Apontar o domínio

Na zona DNS da Hostinger:

- altere o registro `A` com nome `@` para o IPv4 do VPS;
- crie ou altere `www` como `CNAME` apontando para `healthai.net.br`.

Preserve os registros MX, SPF e DKIM da caixa postal da Hostinger. Os registros
antigos `send.mail` e `resend._domainkey.mail` podem ser removidos depois que a
chave do Resend for revogada.

## 3. Enviar o projeto

No servidor:

```bash
git clone https://github.com/GabeCarbone2/healthai.git /opt/healthai
cd /opt/healthai
cp .env.production.example .env.production
```

Edite `.env.production` e preencha `HEALTHAI_SMTP_PASSWORD` com a senha
exclusiva da caixa postal remetente. O arquivo é ignorado pelo Git e não deve
ser enviado ao repositório.

Mantenha `HEALTHAI_CRM_REVOCATION_MODE=hard-fail`. A API usa a lista oficial
do ITI quando `HEALTHAI_ICP_BRASIL_TRUST_ROOTS` fica vazio; nesse caso, o
contêiner precisa de saída HTTPS para a lista e para os serviços de
cadeia/revogação indicados pelos certificados. Se a infraestrutura exigir uma
fonte local, monte um bundle PEM confiável no contêiner e configure o caminho
nessa variável. Nenhuma conta administrativa ou credencial paga do Web Service
do CFM é necessária.

Os artefatos `models/pima_selected.joblib` e
`models/nhanes_selected.joblib` precisam estar versionados no repositório antes
do clone.

## 4. Construir e iniciar

```bash
docker compose -f compose.production.yml up -d --build
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=100
curl --fail https://healthai.net.br/api/ready
```

Quando os registros DNS apontarem para o VPS, o Caddy solicitará e renovará o
certificado HTTPS automaticamente.

O contêiner da API roda sem privilégios, com sistema de arquivos somente para
leitura e volume gravável apenas para o banco. A rota `/api/ready` só responde
com sucesso quando banco, relatório e artefatos estão consistentes.

## 5. Atualizar

```bash
cd /opt/healthai
git pull --ff-only
./deploy/deploy.sh
```

O script valida a configuração, cria backup consistente do SQLite com a API de
backup nativa, constrói e valida a nova imagem antes de substituir a API e
aguarda `/api/ready`. Também existe o workflow manual **Deploy de produção**,
que sincroniza a release sem transferir `.env.production` nem o diretório de
dados. Configure no ambiente `production` do
GitHub os segredos `VPS_HOST`, `VPS_USER`, `VPS_DEPLOY_PATH`,
`VPS_SSH_PRIVATE_KEY` e `VPS_KNOWN_HOSTS` antes de executá-lo.

## Backup

O banco fica no volume `healthai_data`. Além do backup semanal do VPS, faça
snapshots antes de atualizações relevantes. Nunca copie um banco SQLite
enquanto houver uma escrita em andamento; pare a API ou use o comando de backup
do SQLite.
