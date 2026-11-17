# Наш форк — что активно, что нет

Этот файл — только наши пометки поверх апстрима misha-tgshv, не трогает
`README.md` автора (чтобы не ловить конфликты при `git fetch upstream && git merge`).

## Единственный активный профиль: sr_away

Один рабочий профиль `conf/sr_away.conf` (YouTube и зарубежный трафик через VPN, российские сервисы напрямую).
Профиль `sr_home` выведен из эксплуатации и удалён (ноябрь 2026), так как прямой маршрут для YouTube дома более не актуален.

Подписка в приложении (macOS + iOS) — на raw-URL файла `conf/sr_away.conf`.

**Файл сгенерирован, вручную не править.** Источник — шаблон
`tools/profile.base.conf`; сборка и проверка:

```bash
python3 tools/build_profiles.py          # пересобрать файл
python3 tools/build_profiles.py --check  # код 1, если файл в conf/ разошёлся с шаблоном
```

Новое общее правило — в шаблон, затем пересборка, затем `tools/check.sh`, затем commit + push.

**Проверки перед push** (`tools/check.sh`; скрипты и реестр лежат в скилле
`shadowrocket-configs`, путь можно задать `SR_SKILL`):
1. профиль совпадает с шаблоном (`build_profiles.py --check`);
2. линтер `lint_config.py`: ошибки валят проверку, предупреждения показываются;
3. личные правила из реестра на месте;
4. тесты маршрутизации `tests/routes.txt` через `route_sim.py` (ожидаемая политика для
   хостов; формат описан в начале файла). Каждая найденная проблема маршрута должна стать
   строкой в `tests/routes.txt`.

После Update на профиле в приложении: открыть Config → профиль → Preview и, пока окно открыто,
`app_state.py live conf/sr_away.conf` показывает, что в приложении именно то, что в
репозитории (код 0). iCloud-слепок профиля после Update не обновляется, его `diff` не доказательство.
Окно Preview закрывать сразу: пока оно открыто, приложение слушает `*:8080` и принимает запись без
авторизации (подробнее в скилле, `references/app-capabilities.md`).

Модель: всё через прокси по умолчанию, кроме явных исключений. Порядок правил
(первое совпадение побеждает):

```
[Rule]
# --- личные правила (реестр: скилл shadowrocket-configs,
#     references/personal-rules-registry.md) ---
DOMAIN-SUFFIX,brightdata.com,EU-GROUP       # свой прокси-провайдер
DOMAIN-SUFFIX,luminati.io,EU-GROUP
DOMAIN-SUFFIX,brd.superproxy.io,EU-GROUP
IP-CIDR,84.52.113.154/32,DIRECT             # служебный адрес, напрямую
DOMAIN-SUFFIX,reg.ru,DIRECT                 # у API ограничение по IP на домашнюю статику
DOMAIN-SUFFIX,brandpresent.ru,DIRECT        # сайт принимает только российский маршрут
DOMAIN-SUFFIX,5ka.ru,DIRECT                 # X5: сайт, API и авторизация дают 403
DOMAIN-SUFFIX,x5.ru,DIRECT                  #     через зарубежный выход
DOMAIN-SUFFIX,x5id.ru,DIRECT
DOMAIN-SUFFIX,x5club.ru,DIRECT
DOMAIN-SUFFIX,x5static.ru,DIRECT

RULE-SET,.../rules/adblock.list,REJECT      # наш снапшот OISD Small
DOMAIN-SUFFIX,yandex.net,DIRECT              # сервисы Яндекса напрямую; стоят ПОСЛЕ adblock,
DOMAIN-SUFFIX,yandex.ru,DIRECT              #   чтобы реклама Яндекса (mc.yandex.ru, an.yandex.ru) резалась
RULE-SET,.../rules/domains_youtube.list,DIRECT|PROXY   # единственное отличие home/away
RULE-SET,hydraponique/roscomvpn-geoip,DIRECT     # внешняя живая подписка
RULE-SET,hxehex/russia-mobile-internet-whitelist,DIRECT  # внешняя живая подписка
RULE-SET,.../rules/domains_banking.list,DIRECT   # апстрим misha-tgshv, живая ссылка
GEOIP,RU,DIRECT                             # требует GeoLite2 DB в Settings
FINAL,PROXY
```

Правило YouTube стоит после adblock (рекламные домены YouTube всё равно режутся) и
до российских списков (чтобы CDN-узлы googlevideo не ушли по `GEOIP,RU`/IP-списку).
К списку автора добавлены 5 доменов YouTube, которых в нём нет (`jnn-pa.googleapis.com`,
`yt3.googleusercontent.com`, `ytimg.l.google.com`, `yting.com`, `yt-video-upload.l.google.com`; источник
`itdoginfo/allow-domains`, список `YOUTUBE_EXTRA` в `tools/build_profiles.py`); политика та же, что у списка. Явные
правила по домену в любом случае проверяются раньше IP-списков и `GEOIP,RU` (приоритет приложения).
Из шаблона убраны мёртвые строки автора: `dns-fallback-system` (приложение 2.2.92 такой ключ не знает) и
`Israel-Group`/`AUTO` (строки групп в `[General]` приложение не читает).

**`EU-GROUP`** и **`AI-GROUP`** определены в шаблоне, в секции `[Proxy Group]`:
- **`EU-GROUP`**: `url-test` по серверам `SMART-Германия`, `SMART-Нидерланды`, `SMART-Швеция`, `SMART-Франция` (включая вариант с кириллической «М» `SМART-Франция` из подписки), проверка раз в 10 минут. На неё ссылаются три правила Bright Data.
- **`AI-GROUP`**: `url-test` по скоростным серверам с чистой IP-репутацией у Google/OpenAI (`SMART-Нидерланды`, `SMART-Германия`, `SMART-Швеция`, `SМART-Канада`). На неё направлен весь трафик Antigravity, Gemini, Claude, ChatGPT, OpenAI. Изолирует ИИ-инструменты от ручного переключения стран на главном экране (например, при переключении на США).
- В `[General]` включен `block-quic = all-proxy`, принуждающий зарубежный трафик работать по надежному TCP (HTTP/2 по VLESS) вместо нестабильного UDP/QUIC под ТСПУ.

Приложение хранит группы отдельно от профиля и существующую группу при Update не
перезаписывает: после правки `[Proxy Group]` сначала удалить группы в приложении (Home → Proxy Group → «…» →
отметить → Delete), потом Update профиля. Проверка: Home → Proxy Group показывает группы и выбранные узлы.

Полный разбор решений и альтернатив — в скилле `shadowrocket-configs`,
`references/consolidation-2026-09.md` и `references/personal-rules-registry.md`.

## Что здесь чужое, а что наше

Контракт (обновлено 2026-11-17): остаётся единственный профиль `sr_away`. Чужие
профили и правила с GitHub и из других источников мы не используем как есть, а
анализируем и перерабатываем в эти два.

- Удалены из `conf/` 2026-10-16: `sr_ru_whitelist`, `sr_ru_basic`, `sr_ru_geo`,
  `sr_ru_mini`, `sr_ru_keen`, `sr_nonru_basic`, `sr_ru_extended`. Прежнее содержимое
  есть в истории git (последний коммит с ними — `7fc4500`) и в локальном бэкапе
  `~/Projects/_configs/shadowrocket/backups/2026-10-16-fork-conf/`. Старый личный список
  доменов (ИИ-сервисы, независимые медиа) был в `sr_ru_basic.conf` (коммит `583cc9e`).
- `rules/*` (кроме `adblock.list`) — унаследованные копии списков апстрима misha-tgshv,
  не наши файлы. Профили на них **не ссылаются**: списки `domains_banking.list` и
  `domains_youtube.list` берутся по живой ссылке из репозитория автора
  (`raw.githubusercontent.com/misha-tgshv/...`), а из форка профили берут только
  `rules/adblock.list`. Эти копии можно удалять.

## Workflow удалён

`.github/workflows/run.yml` (унаследован от апстрима) удалён 2026-10-16. Он по
расписанию и при каждом push в `main` пересобирал `rules/`, `modules/`, `scripts/` и
`conf/sr_ru_*.conf` из источников автора и коммитил их от имени `github-actions[bot]`;
нашим профилям он ничего не давал (их `adblock.list` он не создаёт), а при запуске
вернул бы удалённые `sr_ru_*.conf`. В форке он ни разу не запускался (0 запусков с
создания форка 2026-09-22). Файл остаётся в истории git (последний коммит с ним —
`6d9f7a7`). Обновлять списки банков и YouTube в форке не нужно: профили ссылаются на
репозиторий автора, где его собственный workflow их обновляет.

## Что наше и требует периодического ручного обновления

- **`rules/adblock.list`** — разовый снапшот `small.oisd.nl` (не живая подписка).
  Живой OISD меняется примерно на 8% записей за 3,5 недели; обновлять раз в 2-3 месяца
  или когда что-то перестало открываться/блокироваться:
  `python3 tools/refresh_adblock.py --dry-run`, затем без `--dry-run`, затем
  `tools/check.sh`. Скрипт откажется писать файл, если источник сломан (мало записей) или
  заблокировал бы личный DIRECT-домен из шаблона.
- **Внешние списки:** раз в месяц `check_sources.py conf/sr_away.conf
  --lock tools/sources.lock.json` (скрипт из скилла): доступность, размер, возраст, дрейф.
  После осознанной проверки добавить `--update-lock` и закоммитить `tools/sources.lock.json`.

## Что обновляется само, трогать не надо

- `hydraponique/roscomvpn-geoip` и `hxehex/russia-mobile-internet-whitelist`
  — внешние живые подписки, авторы обновляют сами.
- `rules/domains_banking.list` и `rules/domains_youtube.list` — апстрим misha-tgshv,
  мы просто ссылаемся на его raw-URL.
- GeoLite2 Country/ASN базы — настроено автообновление в самом приложении
  (Settings → GeoLite2 Database → Auto Background Update), раз в 7 дней.
