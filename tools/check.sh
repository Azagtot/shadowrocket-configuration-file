#!/usr/bin/env bash
# Проверка перед push: сборка, линтер, реестр личных правил, тесты маршрутизации, валидация NAS sing-box.
# Скрипты и реестр лежат в скилле shadowrocket-configs; путь можно задать SR_SKILL.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${SR_SKILL:-}" ]; then
  if [ -d "$HOME/.agents/skills/shadowrocket-configs" ]; then
    SKILL="$HOME/.agents/skills/shadowrocket-configs"
  elif [ -d "$HOME/.codex/skills/shadowrocket-configs" ]; then
    SKILL="$HOME/.codex/skills/shadowrocket-configs"
  else
    SKILL="$HOME/.claude/skills/shadowrocket-configs"
  fi
else
  SKILL="$SR_SKILL"
fi
RAW="https://raw.githubusercontent.com/Azagtot/shadowrocket-configuration-file/main/conf/"
fail=0

echo "== 1/5 профили совпадают с шаблоном"
python3 tools/build_profiles.py --check || fail=1

echo "== 2/5 линтер (ошибки валят проверку, предупреждения только показываем)"
python3 "$SKILL/scripts/lint_config.py" --expect-update-url-prefix "$RAW" conf/sr_away.conf || fail=1

echo "== 3/5 личные правила из реестра на месте"
for f in conf/sr_away.conf; do
  python3 "$SKILL/scripts/inspect_shadowrocks_config.py" --rules "$f" \
    --require "$SKILL/references/personal-rules-registry.md" >/dev/null || { echo "реестр: провал в $f"; fail=1; }
done

echo "== 4/5 тесты маршрутизации"
python3 "$SKILL/scripts/route_sim.py" --tests tests/routes.txt conf/sr_away.conf || fail=1

echo "== 5/5 валидация профиля NAS (sing-box 1.10)"
if ssh -o ConnectTimeout=2 -o BatchMode=yes -o IdentityAgent=none -i "$HOME/.ssh/n54l_ed25519" andrey@192.168.10.5 "exit 0" 2>/dev/null; then
  ssh -o IdentityAgent=none -i "$HOME/.ssh/n54l_ed25519" andrey@192.168.10.5 "cat > /tmp/check-sb.json && /nix/store/3fp3sxj6hjgp72p3h8zsgkg346ar1q3z-sing-box-1.10.1/bin/sing-box check -c /tmp/check-sb.json" < conf/sing-box-nas.json || fail=1
  echo "sing-box 1.10 на Apofis: конфигурация валидна"
else
  python3 -m json.tool conf/sing-box-nas.json >/dev/null || fail=1
  echo "sing-box JSON синтаксис: валиден (Apofis офлайн)"
fi

[ "$fail" = 0 ] && echo "ВСЁ В ПОРЯДКЕ" || { echo "ЕСТЬ ПРОВАЛЫ"; exit 1; }
