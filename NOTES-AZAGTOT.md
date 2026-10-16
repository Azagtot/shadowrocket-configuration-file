# Наш форк — что активно, что нет

Этот файл — только наши пометки поверх апстрима misha-tgshv, не трогает
`README.md` автора (чтобы не ловить конфликты при `git fetch upstream && git merge`).

## Активные профили: sr_home и sr_away

Два профиля с одинаковыми правилами, отличаются только маршрутом YouTube:

| Файл | Где используется | YouTube |
|---|---|---|
| `conf/sr_home.conf` | дома | `DIRECT` |
| `conf/sr_away.conf` | вне дома | `PROXY` |

Подписка в приложении (macOS + iOS) — на raw-URL соответствующего файла.
Переключаются вручную в Config.

**Файлы сгенерированы, вручную не править.** Источник — шаблон
`tools/profile.base.conf`; сборка и проверка:

```bash
python3 tools/build_profiles.py          # пересобрать оба файла
python3 tools/build_profiles.py --check  # код 1, если файлы разошлись с шаблоном
```

Новое общее правило — в шаблон, затем пересборка, затем commit + push.

Модель: всё через прокси по умолчанию, кроме явных исключений. Порядок правил
(первое совпадение побеждает):

```
[Rule]
# --- личные правила (реестр: скилл shadowrocket-configs,
#     references/personal-rules-registry.md) ---
DOMAIN-SUFFIX,brightdata.com,EU-GROUP       # свой прокси-провайдер
DOMAIN-SUFFIX,luminati.io,EU-GROUP
DOMAIN-SUFFIX,brd.superproxy.io,EU-GROUP
IP-CIDR,84.52.113.154/32,DIRECT             # шлюз компании (bastion-проект)
DOMAIN-SUFFIX,reg.ru,DIRECT                 # у API ограничение по IP на домашнюю статику
DOMAIN-SUFFIX,brandpresent.ru,DIRECT        # сайт принимает только российский маршрут
DOMAIN-SUFFIX,5ka.ru,DIRECT                 # X5: сайт, API и авторизация дают 403
DOMAIN-SUFFIX,x5.ru,DIRECT                  #     через зарубежный выход
DOMAIN-SUFFIX,x5id.ru,DIRECT
DOMAIN-SUFFIX,x5club.ru,DIRECT
DOMAIN-SUFFIX,x5static.ru,DIRECT

RULE-SET,.../rules/adblock.list,REJECT      # наш снапшот OISD Small
RULE-SET,.../rules/domains_youtube.list,DIRECT|PROXY   # единственное отличие home/away
RULE-SET,hydraponique/roscomvpn-geoip,DIRECT     # внешняя живая подписка
RULE-SET,hxehex/russia-mobile-internet-whitelist,DIRECT  # внешняя живая подписка
RULE-SET,.../rules/domains_banking.list,DIRECT   # апстрим misha-tgshv, живая ссылка
GEOIP,RU,DIRECT                             # требует GeoLite2 DB в Settings
FINAL,PROXY
```

Правило YouTube стоит после adblock (рекламные домены YouTube всё равно режутся) и
до российских списков (чтобы CDN-узлы googlevideo не ушли по `GEOIP,RU`/IP-списку).

Группа `EU-GROUP` определена в приложении (у самого пользователя), в профилях она
закомментирована в шаблоне автора. Переносить профиль на другое устройство без этой
группы нельзя.

Полный разбор решений и альтернатив — в скилле `shadowrocket-configs`,
`references/consolidation-2026-09.md` и `references/personal-rules-registry.md`.

## Что здесь чужое, а что наше

Контракт (2026-10-16): остаются только два своих профиля, `sr_home` и `sr_away`. Чужие
профили и правила с GitHub и из других источников мы не используем как есть, а
анализируем и перерабатываем в эти два.

- Удалены из `conf/` 2026-10-16: `sr_ru_whitelist`, `sr_ru_basic`, `sr_ru_geo`,
  `sr_ru_mini`, `sr_ru_keen`, `sr_nonru_basic`, `sr_ru_extended`. Прежнее содержимое
  есть в истории git (последний коммит с ними — `7fc4500`) и в локальном бэкапе
  `~/Projects/_configs/shadowrocket/backups/2026-10-16-fork-conf/`. Старый личный список
  доменов (ИИ-сервисы, независимые медиа) был в `sr_ru_basic.conf` (коммит `583cc9e`).
- `rules/*` (кроме `adblock.list`) — списки апстрима misha-tgshv, не наши файлы; на два
  из них ссылаются профили (`domains_banking.list`, `domains_youtube.list`).

## Предупреждение про workflow

`.github/workflows/run.yml` (унаследован от апстрима) запускается по расписанию и при
каждом push в `main` и **заново создаёт** `conf/sr_ru_*.conf` и `conf/sr_nonru_basic.conf`
из шаблона автора (и коммитит их). Если Actions в форке включены и workflow запустится,
эти удалённые файлы вернутся. Файлы `sr_home.conf` и `sr_away.conf` он не трогает (их
имён не знает). На 2026-10-16 запусков не было; решение, отключать ли workflow,
отложено за владельцем.

## Что наше и требует периодического ручного обновления

- **`rules/adblock.list`** — разовый снапшот `small.oisd.nl` (не живая
  подписка). Список блокировок в РФ меняется регулярно — сверять руками
  раз в 2-3 месяца или когда что-то перестало открываться/блокироваться.
  Пересобрать: см. `upstream-fork-workflow.md` в скилле, раздел про
  разовые снапшоты.

## Что обновляется само, трогать не надо

- `hydraponique/roscomvpn-geoip` и `hxehex/russia-mobile-internet-whitelist`
  — внешние живые подписки, авторы обновляют сами.
- `rules/domains_banking.list` и `rules/domains_youtube.list` — апстрим misha-tgshv,
  мы просто ссылаемся на его raw-URL.
- GeoLite2 Country/ASN базы — настроено автообновление в самом приложении
  (Settings → GeoLite2 Database → Auto Background Update), раз в 7 дней.
