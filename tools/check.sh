#!/usr/bin/env bash
# Проверка перед push: сборка, линтер, реестр личных правил, тесты маршрутизации.
# Скрипты и реестр лежат в скилле shadowrocket-configs; путь можно задать SR_SKILL.
set -euo pipefail
cd "$(dirname "$0")/.."
SKILL="${SR_SKILL:-$HOME/.claude/skills/shadowrocket-configs}"
RAW="https://raw.githubusercontent.com/Azagtot/shadowrocket-configuration-file/main/conf/"
fail=0

echo "== 1/4 профили совпадают с шаблоном"
python3 tools/build_profiles.py --check || fail=1

echo "== 2/4 линтер (ошибки валят проверку, предупреждения только показываем)"
python3 "$SKILL/scripts/lint_config.py" --expect-update-url-prefix "$RAW" conf/sr_home.conf conf/sr_away.conf || fail=1

echo "== 3/4 личные правила из реестра на месте"
for f in conf/sr_home.conf conf/sr_away.conf; do
  python3 "$SKILL/scripts/inspect_shadowrocks_config.py" --rules "$f" \
    --require "$SKILL/references/personal-rules-registry.md" >/dev/null || { echo "реестр: провал в $f"; fail=1; }
done

echo "== 4/4 тесты маршрутизации"
python3 "$SKILL/scripts/route_sim.py" --tests tests/routes.txt conf/sr_home.conf conf/sr_away.conf || fail=1

[ "$fail" = 0 ] && echo "ВСЁ В ПОРЯДКЕ" || { echo "ЕСТЬ ПРОВАЛЫ"; exit 1; }
