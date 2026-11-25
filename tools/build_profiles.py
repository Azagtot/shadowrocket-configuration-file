#!/usr/bin/env python3
"""Собирает профили Shadowrocket и sing-box (NAS) из шаблонов.

Активные цели сборки:
  1) conf/sr_away.conf — YouTube и зарубежный трафик через VPN (PROXY), сервисы РФ напрямую.
  2) conf/sing-box-nas.json — sing-box 1.10 для домашнего сервера Apofis (Clash API :9095, Mixed :7890).

Запуск из корня репозитория:
  python3 tools/build_profiles.py          # пересобрать все файлы
  python3 tools/build_profiles.py --check  # код 1, если файлы в conf/ не совпадают с шаблонами
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "profile.base.conf"
NODES_CACHE = ROOT / "tools" / "nodes.cache.json"
RAW = "https://raw.githubusercontent.com"
YOUTUBE_LIST = f"{RAW}/misha-tgshv/shadowrocket-configuration-file/main/rules/domains_youtube.list"

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


def render_sr(file: str, cfg: dict[str, str], template: str) -> str:
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


def render_singbox() -> dict:
    # Загрузка актуальных VLESS Reality нод из кэша подписки
    cached_nodes = []
    if NODES_CACHE.exists():
        try:
            cached_nodes = json.loads(NODES_CACHE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Предупреждение: ошибка чтения {NODES_CACHE}: {e}", file=sys.stderr)

    # Базовые группы маршрутизации sing-box
    standard_outbounds = [
        {
            "type": "urltest",
            "tag": "auto-eu",
            "outbounds": [
                "BRIDGE-Швеция",
                "BRIDGE-Германия",
                "Франция",
                "BRIDGE-Нидерланды",
            ],
            "url": "http://www.gstatic.com/generate_204",
            "interval": "3m",
            "tolerance": 50,
        },
        {
            "type": "selector",
            "tag": "AI-GROUP",
            "outbounds": [
                "SМART-Канада [S+]",
                "SМART-Канада",
                "BRIDGE-Швеция",
                "BRIDGE-Германия",
                "Франция",
                "SМART-Япония",
                "auto-eu",
            ],
            "default": "SМART-Канада [S+]",
        },
        {
            "type": "selector",
            "tag": "PROXY",
            "outbounds": [
                "auto-eu",
                "BRIDGE-Швеция",
                "BRIDGE-Германия",
                "Франция",
                "BRIDGE-Нидерланды",
                "AI-GROUP",
                "direct",
            ],
        },
        {
            "type": "direct",
            "tag": "direct",
            "domain_strategy": "ipv4_only",
        },
        {
            "type": "block",
            "tag": "reject",
        },
    ]

    all_outbounds = standard_outbounds + cached_nodes

    config = {
        "log": {
            "level": "warn",
            "timestamp": True,
        },
        "experimental": {
            "clash_api": {
                "external_controller": "0.0.0.0:9095",
                "external_ui": "ui",
                "secret": "",
                "default_mode": "rule",
            }
        },
        "dns": {
            "servers": [
                {
                    "tag": "remote-dns",
                    "address": "https://1.1.1.1/dns-query",
                    "detour": "AI-GROUP",
                },
                {
                    "tag": "local-dns",
                    "address": "192.168.10.1",
                    "detour": "direct",
                },
            ],
            "rules": [
                {
                    "outbound": "any",
                    "server": "local-dns",
                },
            ],
            "final": "remote-dns",
            "strategy": "ipv4_only",
            "reverse_mapping": True,
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "0.0.0.0",
                "listen_port": 7890,
                "sniff": True,
            },
            {
                "type": "tproxy",
                "tag": "tproxy-in",
                "listen": "0.0.0.0",
                "listen_port": 12345,
                "sniff": True,
                "sniff_override_destination": True,
            },
        ],
        "outbounds": all_outbounds,
        "route": {
            "geoip": {
                "path": "/var/lib/sing-box/geoip.db"
            },
            "rules": [
                {
                    "protocol": "quic",
                    "port": 443,
                    "outbound": "reject",
                },
                {
                    "protocol": "bittorrent",
                    "outbound": "direct",
                },
                # Личные правила Azagtot (1-в-1 с personal-rules-registry.md)
                {
                    "domain_suffix": ["brightdata.com", "luminati.io", "brd.superproxy.io"],
                    "outbound": "auto-eu",
                },
                {
                    "domain_suffix": ["arkoselabs.com"],
                    "outbound": "PROXY",
                },
                {
                    "ip_cidr": ["84.52.113.154/32", "91.190.85.67/32"],
                    "outbound": "direct",
                },
                {
                    "domain_suffix": [
                        "reg.ru",
                        "brandpresent.ru",
                        "5ka.ru",
                        "x5.ru",
                        "x5id.ru",
                        "x5club.ru",
                        "x5static.ru",
                        "yandex.net",
                        "yandex.ru",
                        "nas",
                    ],
                    "outbound": "direct",
                },
                # YouTube (Strictly above AI-GROUP Google catch-all & GeoIP RU)
                {
                    "domain_suffix": [
                        "googlevideo.com",
                        "youtube.com",
                        "ytimg.com",
                        "youtu.be",
                    ] + YOUTUBE_EXTRA,
                    "domain_keyword": ["youtube", "googlevideo"],
                    "outbound": "PROXY",
                },
                # AI Group & All Google Services (sticky single node, zero mid-session jumps)
                {
                    "domain_suffix": [
                        "accounts.google.com",
                        "ai.google",
                        "ai.google.dev",
                        "aiplatform.googleapis.com",
                        "aistudio.google.com",
                        "alkalimakersuite-pa.googleapis.com",
                        "anthropic.com",
                        "antigravity-unleash.goog",
                        "antigravity.google",
                        "autopush-cloudcode-pa.googleapis.com",
                        "chatgpt.com",
                        "claude.ai",
                        "cloud.google",
                        "cloudaicompanion.googleapis.com",
                        "cloudcode-pa.googleapis.com",
                        "daily-cloudcode-pa.googleapis.com",
                        "deepmind.google",
                        "dns.google",
                        "gemini.google",
                        "gemini.google.com",
                        "generativelanguage.googleapis.com",
                        "goog",
                        "google-analytics.com",
                        "google.com",
                        "google.dev",
                        "googleapis.com",
                        "googletagmanager.com",
                        "googleusercontent.com",
                        "gstatic.com",
                        "labs.google",
                        "oaistatic.com",
                        "oaiusercontent.com",
                        "oauth2.googleapis.com",
                        "openai.com",
                        "staging-cloudcode-pa.googleapis.com",
                        "withgoogle.com",
                    ],
                    "domain_keyword": [
                        "antigravity",
                        "cloudaicompanion",
                        "cloudcode",
                        "gemini",
                        "generativelanguage",
                    ],
                    "domain_regex": [
                        "^.*-pa\\.googleapis\\.com$",
                    ],
                    "outbound": "AI-GROUP",
                },
                # Fallback GeoIP RU
                {
                    "geoip": "ru",
                    "outbound": "direct",
                },
                # Final fallback
                {
                    "outbound": "PROXY",
                },
            ]
        },
    }
    return config


def main() -> int:
    check = "--check" in sys.argv[1:]
    template = TEMPLATE.read_text(encoding="utf-8")
    bad = 0

    # 1. Shadowrocket Profiles
    for file, cfg in PROFILES.items():
        text = render_sr(file, cfg, template)
        assert "{{" not in text, f"{file}: остались незаполненные поля"
        target = ROOT / "conf" / file
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != text:
                print(f"РАСХОЖДЕНИЕ: {target.relative_to(ROOT)}")
                bad = 1
        else:
            target.write_text(text, encoding="utf-8")
            print(f"записан {target.relative_to(ROOT)}")

    # 2. sing-box Profile for NAS
    sb_target = ROOT / "conf" / "sing-box-nas.json"
    sb_json_text = json.dumps(render_singbox(), indent=2, ensure_ascii=False) + "\n"
    if check:
        if not sb_target.exists() or sb_target.read_text(encoding="utf-8") != sb_json_text:
            print(f"РАСХОЖДЕНИЕ: {sb_target.relative_to(ROOT)}")
            bad = 1
    else:
        sb_target.write_text(sb_json_text, encoding="utf-8")
        print(f"записан {sb_target.relative_to(ROOT)}")

    return bad


if __name__ == "__main__":
    raise SystemExit(main())
