#!/usr/bin/env python3
"""Собирает профиль Shadowrocket из шаблона tools/profile.base.conf.

Единственный активный профиль:
  conf/sr_away.conf — YouTube и зарубежный трафик через VPN (PROXY), сервисы РФ напрямую.

Запуск из корня репозитория:
  python3 tools/build_profiles.py          # пересобрать файл
  python3 tools/build_profiles.py --check  # код 1, если файл в conf/ не совпадает с шаблоном
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "profile.base.conf"
RAW = "https://raw.githubusercontent.com"
YOUTUBE_LIST = f"{RAW}/misha-tgshv/shadowrocket-configuration-file/main/rules/domains_youtube.list"
# Домены YouTube, которых нет в списке автора (он покрывает остальное ключевыми словами youtube/googlevideo).
# Источник: itdoginfo/allow-domains, Services/youtube.lst (сверка 2026-10-16). Политика та же, что у списка.
YOUTUBE_EXTRA = [
    "jnn-pa.googleapis.com",
    "yt3.googleusercontent.com",
    "ytimg.l.google.com",
    "yting.com",
    "yt-video-upload.l.google.com",
]
UPDATE_URL = f"{RAW}/Azagtot/shadowrocket-configuration-file/main/conf/{{file}}"

PROFILES = {
    "sr_away.conf": {
        "name": "sr_away",
        "desc": "YouTube и зарубежный трафик через VPN, сервисы РФ напрямую",
        "policy": "PROXY",
        "comment": "# YouTube: через VPN. Правило стоит до GEOIP,RU и RU-whitelist, чтобы\n"
                   "# российские CDN-узлы googlevideo не ушли напрямую",
    },
}


def render(file: str, cfg: dict[str, str], template: str) -> str:
    extra = "".join(f"DOMAIN-SUFFIX,{d},{cfg['policy']}\n" for d in YOUTUBE_EXTRA)
    youtube = (
        f"{cfg['comment']}\nRULE-SET,{YOUTUBE_LIST},{cfg['policy']}\n"
        f"# Дополнительные домены YouTube, которых нет в списке автора (itdoginfo/allow-domains)\n{extra}"
    )
    return (
        template.replace("{{NAME}}", cfg["name"])
        .replace("{{DESC}}", cfg["desc"])
        .replace("{{UPDATE_URL}}", UPDATE_URL.format(file=file))
        .replace("{{YOUTUBE}}\n", youtube)
    )


def main() -> int:
    check = "--check" in sys.argv[1:]
    template = TEMPLATE.read_text(encoding="utf-8")
    bad = 0
    for file, cfg in PROFILES.items():
        text = render(file, cfg, template)
        assert "{{" not in text, f"{file}: остались незаполненные поля"
        target = ROOT / "conf" / file
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                print(f"РАСХОЖДЕНИЕ: {target.relative_to(ROOT)}")
                bad = 1
        else:
            target.write_text(text, encoding="utf-8")
            print(f"записан {target.relative_to(ROOT)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
