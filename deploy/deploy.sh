#!/usr/bin/env sh
set -eu

COMPOSE_FILE="compose.production.yml"

if [ ! -f .env.production ]; then
  echo "Arquivo .env.production ausente; deploy cancelado." >&2
  exit 1
fi

docker compose -f "$COMPOSE_FILE" config --quiet

if docker compose -f "$COMPOSE_FILE" ps --status running api \
  | grep -q api; then
  docker compose -f "$COMPOSE_FILE" exec -T api python -c '
import datetime
import sqlite3
from pathlib import Path

source = Path("/app/data/healthai.db")
if source.exists():
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"healthai-{stamp}.db"
    with sqlite3.connect(source) as origin, sqlite3.connect(destination) as target:
        origin.backup(target)
    print(f"Backup criado: {destination}")
    for stale in sorted(backup_dir.glob("healthai-*.db"), reverse=True)[10:]:
        stale.unlink()
'
fi

docker compose -f "$COMPOSE_FILE" build

# Volumes criados por versões antigas podem pertencer a root. Ajusta somente o
# volume persistente para o usuário sem privilégios da imagem atual.
api_container=$(docker compose -f "$COMPOSE_FILE" ps -aq api)
if [ -n "$api_container" ]; then
  data_volume=$(
    docker inspect "$api_container" \
      --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}'
  )
  if [ -n "$data_volume" ]; then
    docker run --rm --user root -v "$data_volume:/app/data" \
      healthai-api:latest \
      chown -R healthai:healthai /app/data
  fi
fi

docker compose -f "$COMPOSE_FILE" run --rm --no-deps api \
  python -c 'from backend.settings import validate_production_settings; validate_production_settings()'
# Compose v5 pode falhar ao inspecionar o manifest list substituído pela nova
# build. A imagem já foi validada; remove os contêineres antigos antes da troca.
docker compose -f "$COMPOSE_FILE" rm --stop --force api web
docker compose -f "$COMPOSE_FILE" up -d --no-build --remove-orphans
docker compose -f "$COMPOSE_FILE" ps

attempt=0
until curl --fail --silent --show-error \
  https://healthai.net.br/api/ready >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 12 ]; then
    echo "Readiness não respondeu após 60 segundos." >&2
    docker compose -f "$COMPOSE_FILE" logs --tail=120 api web >&2
    exit 1
  fi
  sleep 5
done

echo "Deploy concluído e serviço pronto."
