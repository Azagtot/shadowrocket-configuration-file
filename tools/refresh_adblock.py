#!/usr/bin/env python3
"""Обновляет снапшот rules/adblock.list из OISD small (разовый импорт, не живая подписка).

  python3 tools/refresh_adblock.py --dry-run     # только показать, что изменилось
  python3 tools/refresh_adblock.py               # перезаписать rules/adblock.list

Защита от плохих данных (скрипт прерывается с кодом 1 и НИЧЕГО не пишет):
  * записей меньше 20000 или меньше 70% от текущего списка (источник мог сломаться);
  * какая-либо запись блокирует домен из личных DIRECT-правил шаблона
    (tools/profile.base.conf: DOMAIN/DOMAIN-SUFFIX ... DIRECT), то есть сломала бы нужный сайт.
Формат источника: «домены без *.», запись example.com блокирует и example.com, и поддомены,
поэтому в Shadowrocket каждая запись превращается в DOMAIN-SUFFIX.
Рекомендуемая периодичность: раз в 2-3 месяца (см. NOTES-AZAGTOT.md).
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URL = "https://small.oisd.nl/domainswild2"
TARGET = ROOT / "rules" / "adblock.list"
TEMPLATE = ROOT / "tools" / "profile.base.conf"
DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")


def protected_domains() -> set[str]:
    out: set[str] = set()
    in_rule = False
    for raw in TEMPLATE.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s.startswith("["):
            in_rule = s.lower() == "[rule]"
            continue
        if in_rule and s and not s.startswith("#"):
            p = [x.strip() for x in s.split(",")]
            if len(p) >= 3 and p[0].upper() in ("DOMAIN", "DOMAIN-SUFFIX") and p[2].upper() == "DIRECT":
                out.add(p[1].lower())
    return out


def current_entries() -> set[str]:
    if not TARGET.exists():
        return set()
    return {
        ln.split(",", 1)[1].strip().lower()
        for ln in TARGET.read_text(encoding="utf-8").splitlines()
        if ln.startswith("DOMAIN-SUFFIX,")
    }


def blocks(entry: str, domain: str) -> bool:
    return domain == entry or domain.endswith("." + entry)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--url", default=SOURCE_URL)
    args = ap.parse_args()

    req = urllib.request.Request(args.url, headers={"User-Agent": "adblock-refresh"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8", "replace")

    meta = dict(re.findall(r"^# (Version|Last modified|Entries): (.+)$", body, re.M))
    entries: set[str] = set()
    bad = 0
    for ln in body.splitlines():
        s = ln.strip().lower()
        if not s or s.startswith("#"):
            continue
        s = s.lstrip("*.")
        if DOMAIN_RE.match(s):
            entries.add(s)
        else:
            bad += 1

    old = current_entries()
    added, removed = sorted(entries - old), sorted(old - entries)
    print(f"источник: {args.url}  версия {meta.get('Version', '?')}  изменён {meta.get('Last modified', '?')}")
    print(f"записей: было {len(old)}, стало {len(entries)} (добавлено {len(added)}, убрано {len(removed)}), строк пропущено {bad}")
    if added:
        print("  примеры добавленных:", ", ".join(added[:6]))
    if removed:
        print("  примеры убранных:   ", ", ".join(removed[:6]))

    problems: list[str] = []
    if len(entries) < 20000:
        problems.append(f"слишком мало записей ({len(entries)} < 20000)")
    if old and len(entries) < 0.7 * len(old):
        problems.append(f"записей {len(entries)} меньше 70% от текущих {len(old)}")
    prot = protected_domains()
    hits = sorted((d, e) for d in prot for e in entries if blocks(e, d))
    for d, e in hits:
        problems.append(f"запись `{e}` заблокировала бы личный DIRECT-домен `{d}`")
    if problems:
        print("ОТКАЗ, файл не изменён:", *problems, sep="\n  - ")
        return 1

    if args.dry_run:
        print("dry-run: файл не записан")
        return 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = (
        "# NAME: adblock.list\n"
        "# SOURCE: https://oisd.nl/ (small list, official domainswild2 format)\n"
        f"# SNAPSHOT: {now} (версия источника {meta.get('Version', '?')}) — не живая подписка, разовый импорт для ручного контроля\n"
        "# LICENSE: см. https://github.com/sjhgvr/oisd/blob/main/LICENSE\n"
        f"# TOTAL: {len(entries)}\n\n"
    )
    TARGET.write_text(header + "\n".join(f"DOMAIN-SUFFIX,{d}" for d in sorted(entries)) + "\n", encoding="utf-8")
    print(f"записан {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
