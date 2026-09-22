# message-service (HR)

Сервис уведомлений HR-платформы: личные сообщения, каналы, WebSocket, Web Push и разбор HR-событий из RabbitMQ.

Принимает только HR-события:

- `hr.event.created` — личное сообщение и отложенный Telegram (`hr.event.notify`)
- `hr.hiring_request.created` — немедленный Telegram
- `message.hiring_request.created`, `message.adaptation.talk_hr`, `message.adaptation.notification` — уведомления по ролям

События логистики (рейсы, машины, простои, TMS) игнорируются.

Сборка образа: `docker build -t hr-platform/message-service:dev .`
