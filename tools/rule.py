#!/usr/bin/env python3
"""CLI утилита для синхронного управления правилами Shadowrocket и sing-box (NAS).

Единая точка управления (SSOT):
  Любое добавленное правило автоматически попадает в:
    1) Реестр личных правил: references/personal-rules-registry.md
    2) Шаблон Shadowrocket: tools/profile.base.conf
    3) Скомпилированный профиль: conf/sr_away.conf
    4) Скомпилированный профиль NAS: conf/sing-box-nas.json

Использование:
  python3 tools/rule.py list                         # показать список личных правил
  python3 tools/rule.py add <domain> <POLICY>        # добавить правило (DIRECT, PROXY, EU-GROUP, AI-GROUP)
  python3 tools/rule.py build                        # пересобрать все конфигурации
  python3 tools/rule.py check                        # запустить полный цикл валидации
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_CONF = ROOT / "tools" / "profile.base.conf"
BUILD_SCRIPT = ROOT / "tools" / "build_profiles.py"
CHECK_SCRIPT = ROOT / "tools" / "check.sh"

VALID_POLICIES = {"DIRECT", "PROXY", "REJECT", "EU-GROUP", "AI-GROUP"}


def find_registry_path() -> Path:
    candidates = [
        Path.home() / ".agents" / "skills" / "shadowrocket-configs" / "references" / "personal-rules-registry.md",
        Path.home() / ".codex" / "skills" / "shadowrocket-configs" / "references" / "personal-rules-registry.md",
        Path.home() / ".claude" / "skills" / "shadowrocket-configs" / "references" / "personal-rules-registry.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def get_personal_rules(reg_path: Path) -> list[str]:
    if not reg_path.exists():
        return []
    lines = reg_path.read_text(encoding="utf-8").splitlines()
    rules = []
    in_block = False
    for l in lines:
        if l.strip() == "```rules":
            in_block = True
            continue
        if in_block:
            if l.strip() == "```":
                break
            if l.strip() and not l.startswith("#"):
                rules.append(l.strip())
    return rules


def cmd_list(args: argparse.Namespace) -> int:
    reg_path = find_registry_path()
    rules = get_personal_rules(reg_path)
    print(f"Личные правила из реестра ({reg_path.name}): {len(rules)} шт.")
    for r in rules:
        parts = r.split(",")
        if len(parts) >= 3:
            print(f"  • {parts[1]:<35} -> {parts[2]}")
        else:
            print(f"  • {r}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    res = subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT)
    return res.returncode


def cmd_check(args: argparse.Namespace) -> int:
    res = subprocess.run(["bash", str(CHECK_SCRIPT)], cwd=ROOT)
    return res.returncode


def cmd_add(args: argparse.Namespace) -> int:
    target = args.target.strip()
    policy = args.policy.strip().upper()

    if policy not in VALID_POLICIES:
        print(f"Ошибка: неизвестная политика '{policy}'. Допустимые: {', '.join(sorted(VALID_POLICIES))}", file=sys.stderr)
        return 1

    # Определение типа правила
    if "/" in target:
        rule_str = f"IP-CIDR,{target},{policy}"
    else:
        rule_str = f"DOMAIN-SUFFIX,{target},{policy}"

    reg_path = find_registry_path()
    rules = get_personal_rules(reg_path)
    if rule_str in rules:
        print(f"Правило '{rule_str}' уже есть в реестре.")
    else:
        # Добавление в реестр
        reg_text = reg_path.read_text(encoding="utf-8")
        if "```rules\n" in reg_text:
            reg_text = reg_text.replace("```rules\n", f"```rules\n{rule_str}\n", 1)
            reg_path.write_text(reg_text, encoding="utf-8")
            print(f"Добавлено в реестр: {reg_path}")

    # Добавление в profile.base.conf
    base_text = BASE_CONF.read_text(encoding="utf-8")
    marker = "# Наши локальные добавления (Azagtot) — не из апстрима misha-tgshv\n"
    if marker in base_text and rule_str not in base_text:
        base_text = base_text.replace(marker, f"{marker}{rule_str}\n", 1)
        BASE_CONF.write_text(base_text, encoding="utf-8")
        print(f"Добавлено в шаблон: {BASE_CONF.relative_to(ROOT)}")

    # Автоматическая пересборка и валидация
    print("Пересобираем профили...")
    b_res = subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT)
    if b_res.returncode != 0:
        return b_res.returncode

    print("Запускаем тесты и линтер...")
    c_res = subprocess.run(["bash", str(CHECK_SCRIPT)], cwd=ROOT)
    return c_res.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Управление правилами SSOT")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Список личных правил")
    sub.add_parser("build", help="Собрать все профили (Shadowrocket + sing-box)")
    sub.add_parser("check", help="Запустить валидацию и тесты")

    add_p = sub.add_parser("add", help="Добавить новое правило")
    add_p.add_argument("target", help="Домен или IP-CIDR (например: example.com или 1.2.3.4/32)")
    add_p.add_argument("policy", help="Политика: DIRECT, PROXY, EU-GROUP, AI-GROUP, REJECT")

    args = parser.parse_args()
    if args.cmd == "list":
        return cmd_list(args)
    elif args.cmd == "build":
        return cmd_build(args)
    elif args.cmd == "check":
        return cmd_check(args)
    elif args.cmd == "add":
        return cmd_add(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
