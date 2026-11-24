#!/usr/bin/env python3
"""Парсер подписки Velvet VPN (VLESS XTLS Reality).

Извлекает узлы и генерирует валидные конфигурации:
  1) Для Shadowrocket: узлы с параметрами фрагментации fm={...}
  2) Для sing-box: чистые VLESS Reality outbounds (uTLS, без неподдерживаемых полей)

Использование:
  python3 tools/parse_subscription.py --url "<url>" --output-singbox outbounds.json
  python3 tools/parse_subscription.py --file sub.txt --summary
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_SUB_URL = "https://sunmoss.net/m4fgm1ijom"


def fetch_subscription(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Shadowrocket/1990 (iOS; Darwin)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    text = data.decode("utf-8", errors="ignore").strip()
    if not text.startswith("vless://"):
        try:
            decoded = base64.b64decode(text).decode("utf-8", errors="ignore")
            if "vless://" in decoded:
                return decoded
        except Exception:
            pass
    return text


def parse_vless_uri(uri: str) -> dict | None:
    uri = uri.strip()
    if not uri.startswith("vless://"):
        return None
    try:
        parts = uri[8:].split("#", 1)
        raw_target = parts[0]
        raw_name = urllib.parse.unquote(parts[1]) if len(parts) > 1 else "Unknown"

        # Очистка имени от флагов/эмодзи в начале
        clean_name = re.sub(r"^[^\w\s]*\s*", "", raw_name).strip()

        # Разбор userinfo@host:port?query
        at_split = raw_target.split("@", 1)
        if len(at_split) != 2:
            return None
        uuid = at_split[0]
        rest = at_split[1]

        q_split = rest.split("?", 1)
        host_port = q_split[0]
        query_str = q_split[1] if len(q_split) > 1 else ""

        if ":" not in host_port:
            return None
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str)

        query = urllib.parse.parse_qs(query_str)
        security = query.get("security", ["none"])[0]
        flow = query.get("flow", [""])[0]
        sni = query.get("sni", [host])[0]
        fp = query.get("fp", ["firefox"])[0]
        pbk = query.get("pbk", [""])[0]
        sid = query.get("sid", [""])[0]
        fm = query.get("fm", [""])[0]

        return {
            "raw_uri": uri,
            "raw_name": raw_name,
            "name": clean_name,
            "uuid": uuid,
            "host": host,
            "port": port,
            "security": security,
            "flow": flow,
            "sni": sni,
            "fp": fp,
            "pbk": pbk,
            "sid": sid,
            "fm": fm,
        }
    except Exception as e:
        print(f"Ошибка парсинга строки VLESS: {e}", file=sys.stderr)
        return None


def to_singbox_outbound(node: dict) -> dict:
    outbound = {
        "type": "vless",
        "tag": node["name"],
        "server": node["host"],
        "server_port": node["port"],
        "uuid": node["uuid"],
    }
    if node["flow"]:
        outbound["flow"] = node["flow"]

    tls_cfg = {
        "enabled": True,
        "server_name": node["sni"],
        "utls": {
            "enabled": True,
            "fingerprint": node["fp"] or "firefox",
        },
    }

    if node["security"] == "reality":
        reality_cfg = {
            "enabled": True,
            "public_key": node["pbk"],
        }
        if node["sid"]:
            reality_cfg["short_id"] = node["sid"]
        tls_cfg["reality"] = reality_cfg

    outbound["tls"] = tls_cfg
    return outbound


def main() -> int:
    parser = argparse.ArgumentParser(description="Парсер подписки Velvet VPN")
    parser.add_argument("--url", default=os.getenv("VELVET_SUB_URL", DEFAULT_SUB_URL), help="URL подписки")
    parser.add_argument("--file", help="Файл со списком vless:// ссылок")
    parser.add_argument("--output-singbox", help="Путь для сохранения outbounds JSON sing-box")
    parser.add_argument("--summary", action="store_true", help="Вывести сводку по узлам")

    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = fetch_subscription(args.url)

    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("vless://")]
    nodes = []
    seen_names = {}

    for l in lines:
        node = parse_vless_uri(l)
        if not node:
            continue
        # Обеспечение уникальности тегов для sing-box
        name = node["name"]
        if name in seen_names:
            seen_names[name] += 1
            node["name"] = f"{name} #{seen_names[name]}"
        else:
            seen_names[name] = 1
        nodes.append(node)

    if args.summary:
        print(f"Успешно распарсено {len(nodes)} узлов:")
        for n in nodes:
            print(f"  • {n['name']:<30} | {n['security']:<7} | {n['host']}:{n['port']}")

    if args.output_singbox:
        sb_outbounds = [to_singbox_outbound(n) for n in nodes]
        out_path = Path(args.output_singbox)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(sb_outbounds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Сохранено {len(sb_outbounds)} outbounds в {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
