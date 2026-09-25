# HR Platform frontend

React-приложение подготовлено для публикации как GitHub Pages project site:

`https://artem130807.github.io/Hr_Project/`

## Локальный запуск

```bash
npm ci
npm start
```

В режиме разработки запросы `/v1` проксируются на API из `src/setupProxy.js`.

## Автоматическая публикация

Workflow `.github/workflows/deploy-frontend-pages.yml` при каждом изменении
`frontend` в ветке `main`:

1. устанавливает зависимости через `npm ci`;
2. запускает тесты;
3. собирает приложение с базовым путём `/Hr_Project`;
4. направляет API-запросы на `https://hr-platform.alt-cargo.tw1.ru`;
5. публикует папку `frontend/build` в GitHub Pages.

Перед первым деплоем откройте в репозитории **Settings → Pages** и выберите
**Source: GitHub Actions**. Затем отправьте изменения в ветку `main` либо вручную
запустите workflow **Deploy frontend to GitHub Pages** во вкладке Actions.

Прямые ссылки на внутренние страницы поддерживаются через `build/404.html`.
Файл `.nojekyll` отключает обработку собранных файлов Jekyll.

## Важное условие для API

GitHub Pages размещает только статический frontend и не может проксировать `/v1`.
Поэтому production-сборка обращается к API напрямую. Бэкенд должен разрешать CORS
для origin `https://artem130807.github.io`. Если origin не разрешён, интерфейс
откроется, но браузер заблокирует запросы к API.

Сервис уведомлений также требует отдельного публичного HTTPS/WSS-адреса. Когда он
будет доступен, добавьте в шаг сборки workflow переменные
`REACT_APP_MESSAGE_SERVICE_URL` и `REACT_APP_MESSAGE_SERVICE_WS_URL`.
