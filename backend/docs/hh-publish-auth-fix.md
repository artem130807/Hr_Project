# Публикация на HH.ru: отчёт по ошибке auth

**Источник:** ответ прокси database-service. Код в git и код в поде — разные вещи, пока образ не выкатили.

## Вердикт

На кластере крутится **устаревший образ hh-service**.  
`database-service` уже новый (прокси + диагностика), `hh-service` — старый (нет dual-auth и `/v1/proxy-auth-info`).

Обычный push в `main` сам под не обновляет: образ hh-service нужно пересобрать и выкатить. **Код в git ≠ код в поде.**

Типичный ответ UI:

```text
Ошибка публикации: hh-service отклонил авторизацию прокси публикации. ...
Попытки: probe: HTTP 404; internal[0]: HTTP 404; jwt: HTTP 401.
hh-service НЕ содержит /v1/proxy-auth-info — образ устарел...
Ответ hh-service: Could not validate credentials
```

| Попытка | Код | Значение |
|--------|-----|----------|
| `probe: /v1/proxy-auth-info` | 404 | Эндпоинта нет → образ hh-service без dual-v2 |
| `internal[0]: /v1/internal/vacancy/{id}` | 404 | Нет internal-маршрутов → тот же устаревший образ |
| `jwt: /v1/vacancy/{id}` | 401 | Старый JWT/JWKS-путь; `Could not validate credentials` |
| Секретов на database-service | 1 | Секрет на DB есть; проблема не в «пустом» секрете на DB |

Это **не** OAuth-токены HH.ru и **не** сессия HR-пользователя. Ломается только service-to-service auth **DB → HH**.

---

## Почему push в main не чинит прод

Образ hh-service нужно пересобрать и выкатить отдельно от database-service. Push в git сам под не обновляет.

| Шаг | Что должно произойти | Типичный сбой |
|-----|----------------------|---------------|
| 1. `build-hh-service` | Kaniko → `registry…/hh-service:SHA` и `:latest` | Job failed / skipped; cache; образ не в registry |
| 2. `build-database-service` | Новый DB-образ (уже на проде) | Успешен → поэтому ошибка уже «новая» и подробная |
| 3. Выкат | Новый тег образа в Deployment `hh-service` | Под остался на старом image |

**Ключевой факт:** пока Deployment `hh-service` смотрит на старый тег, под останется на старом коде — даже после push в git.

Образы собираются из Dockerfile этого репозитория и тегируются как `hr-platform/backend/<service>:<tag>`. В `k8s/manifests.yaml` нет приватного registry и pull-secret.

---

## Пошаговое исправление

### Шаг 0. Зафиксировать текущее состояние

**Локально** соберите образ и сверьте тег в кластере:

```bash
docker build -t hr-platform/backend/hh-service:dev -f services/hh-service/Dockerfile services/hh-service
```

**В кластере:**

```bash
kubectl -n hr-prod get deploy hh-service database-service -o wide

kubectl -n hr-prod get pods -l 'app in (hh-service,database-service)' -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\t"}{.status.containerStatuses[0].imageID}{"\n"}{end}'

kubectl -n hr-prod describe deploy hh-service | findstr /i "Image ImagePull"
```

Сравните SHA/digest `hh-service` с SHA коммита, где есть `proxy-auth-info` (dual-auth). Если digest старый — деплой hh не случился.

---

### Шаг 1. Убедиться, что нужный код в main и в образе

В репозитории backend на `main` должны быть:

- `verify_external_or_internal`
- `/v1/internal/vacancy/*`
- `/v1/proxy-auth-info`

```bash
# в services/hh-service
rg -n "proxy-auth-info|verify_external_or_internal|internal_router" main.py app/utils/auth.py
```

Пересоберите и выкатите именно hh-service. Обновление database-service само по себе образ hh не меняет.

---

### Шаг 2. Заставить кластер взять новый hh-service

#### Предпочтительно (как задумано CI)

1. Собрать образ `hr-platform/backend/hh-service` из Dockerfile этого репозитория.
2. Выставить тот же тег в Deployment и дождаться нового ReplicaSet.

#### Если выкат застрял — принудительный rollout

```bash
# подставьте тег собранного образа hh-service
kubectl -n hr-prod set image deploy/hh-service \
  hh-service=hr-platform/backend/hh-service:<TAG>

kubectl -n hr-prod rollout status deploy/hh-service
kubectl -n hr-prod rollout restart deploy/hh-service
kubectl -n hr-prod rollout status deploy/hh-service
```

**Важно:** `imagePullPolicy: Always` при теге `:latest` не гарантирует обновление, если Deployment держит другой тег. Смотрите `image` в Deployment.

---

### Шаг 3. Секреты (после того как образ новый)

На **обоих** подах должен совпадать хотя бы один из:

- `INTERNAL_PROXY_SECRET`
- `HH_SERVICE_CLIENT_SECRET`
- `DB_CLIENT_SECRET` (fallback)

```bash
kubectl -n hr-prod get secret hr-app-secret -o yaml
# проверьте наличие ключей (значения не светить в чат/тикеты)

kubectl -n hr-prod exec deploy/hh-service -- printenv | findstr /i "INTERNAL_PROXY HH_SERVICE_CLIENT DB_CLIENT"
kubectl -n hr-prod exec deploy/database-service -- printenv | findstr /i "INTERNAL_PROXY HH_SERVICE_CLIENT DB_CLIENT"
```

Сейчас **404 на internal важнее секрета**: даже идеальный секрет не поможет на старом образе без маршрута. Секрет чините **после** появления probe `200`.

---

### Шаг 4. Проверка «образ новый» (обязательно до UI)

Из пода `database-service` (cluster-internal, без ingress `/hh`):

```bash
kubectl -n hr-prod exec deploy/database-service -- \
  wget -qO- http://hh-service:8003/v1/proxy-auth-info

# ожидание:
# {"ok":true,"proxy_auth":"dual-v2","internal_routes":true,"internal_secret_configured":true,...}
```

| Ответ | Вывод | Действие |
|-------|--------|----------|
| HTTP 404 | Образ всё ещё старый | Шаг 2: тег образа в Deployment |
| 200, `internal_secret_configured: false` | Образ новый, секрета нет | Шаг 3: добавить секрет, restart обоих |
| 200, secret true | Auth-слой готов | Пробовать «На HH.ru» в UI |

---

### Шаг 5. Проверка публикации в UI

Hard refresh (Ctrl+F5) → Вакансии → «На HH.ru».

| Сообщение | Слой | Что делать |
|-----------|------|------------|
| probe/internal 404 или dual-auth… | Всё ещё старый hh | Вернуться к шагу 2 |
| Invalid internal proxy token / секрет | Образы ок, secret mismatch | Шаг 3 |
| HH token / HH API Error | Auth сервисов ок | Переавторизовать HH OAuth в сайдбаре |
| Описание короче 200 символов / нет роли | Валидация вакансии | Дописать описание и professional role |
| Успех + ссылка `hh.ru/vacancy/…` | Готово | — |

---

## Чеклист «готово»

| # | Проверка | Ок когда |
|---|----------|----------|
| 1 | Образ `hr-platform/backend/hh-service` | собран из текущего кода |
| 2 | Deployment `hh-service` | `image` = этот тег |
| 4 | Pod `hh-service` | пересоздан после bump; Running |
| 5 | `GET http://hh-service:8003/v1/proxy-auth-info` | 200 + `proxy_auth: dual-v2` |
| 6 | Секрет на DB и HH | одинаковый непустой candidate |
| 7 | UI публикация | нет `Could not validate credentials` |

---

## Кратко

Чинится не «ещё одним пушем ради пуша», а **гарантированным обновлением пода hh-service** до образа с dual-auth.

Пока probe даёт **404** — hh-service на проде старый.  
Пока не будет **200** на `/v1/proxy-auth-info`, кнопка «На HH.ru» будет падать на auth.

### Связанные пути

- `services/hh-service/Dockerfile` — локальная сборка образа `hr-platform/backend/hh-service`
- `services/hh-service/main.py` — `/v1/proxy-auth-info`
- `services/database-service/.../vacancies.py` — proxy `POST/PUT/DELETE /v1/vacancy/{id}/hh`
