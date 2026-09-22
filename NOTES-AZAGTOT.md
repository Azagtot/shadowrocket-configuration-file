# Наш форк — что активно, что нет

Этот файл — только наши пометки поверх апстрима misha-tgshv, не трогает
`README.md` автора (чтобы не ловить конфликты при `git fetch upstream && git merge`).

## Активный профиль

**`conf/sr_ru_whitelist.conf`** — единственный профиль, который реально
используется в приложении (macOS + iOS, подписка на raw-URL этого файла).

Модель: всё через прокси по умолчанию, кроме явных исключений —
```
[Rule]
DOMAIN-SUFFIX,brightdata.com,EU-GROUP       # свой прокси-провайдер
DOMAIN-SUFFIX,luminati.io,EU-GROUP
DOMAIN-SUFFIX,brd.superproxy.io,EU-GROUP
IP-CIDR,84.52.113.154/32,DIRECT             # шлюз компании (bastion-проект)

RULE-SET,.../rules/adblock.list,REJECT      # наш снапшот OISD Small
RULE-SET,hydraponique/roscomvpn-geoip,DIRECT     # внешняя живая подписка
RULE-SET,hxehex/russia-mobile-internet-whitelist,DIRECT  # внешняя живая подписка
RULE-SET,.../rules/domains_banking.list,DIRECT   # апстрим misha-tgshv, живая ссылка
GEOIP,RU,DIRECT                             # требует GeoLite2 DB в Settings
FINAL,PROXY
```

Полный разбор решения и альтернатив — в скилле `shadowrocket-configs`,
`references/consolidation-2026-09.md`.

## Что не активно, но оставлено

- `conf/sr_ru_basic.conf` — **не используется** как профиль в приложении.
  Хранит старый личный список доменов (AI-сервисы, независимые медиа) из
  прошлой модели (DIRECT-по-умолчанию), сохранён коммитом `583cc9e` как
  историческая копия, не как рабочий конфиг. Если понадобится вернуться к
  DIRECT-модели — брать оттуда.
- `conf/sr_ru_geo.conf`, `conf/sr_ru_mini.conf`, `conf/sr_ru_keen.conf`,
  `conf/sr_nonru_basic.conf`, `conf/sr_ru_extended.conf` — чистый апстрим,
  не редактировались, не используются. Оставлены как есть — не удаляем,
  чтобы не плодить конфликты при будущих merge с апстримом.
- `rules/*` (кроме `adblock.list`) — апстрим misha-tgshv, не наши файлы.

## Что наше и требует периодического ручного обновления

- **`rules/adblock.list`** — разовый снапшот `small.oisd.nl` (не живая
  подписка). Список блокировок в РФ меняется регулярно — сверять руками
  раз в 2-3 месяца или когда что-то перестало открываться/блокироваться.
  Пересобрать: см. `upstream-fork-workflow.md` в скилле, раздел про
  разовые снапшоты.

## Что обновляется само, трогать не надо

- `hydraponique/roscomvpn-geoip` и `hxehex/russia-mobile-internet-whitelist`
  — внешние живые подписки, авторы обновляют сами.
- `rules/domains_banking.list` — апстрим misha-tgshv обновляет ежедневно
  (GitHub Actions), мы просто ссылаемся на его raw-URL.
- GeoLite2 Country/ASN базы — настроено автообновление в самом приложении
  (Settings → GeoLite2 Database → Auto Background Update), раз в 7 дней.
