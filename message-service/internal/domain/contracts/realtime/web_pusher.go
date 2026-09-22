package realtime

import (
	"context"

	"github.com/google/uuid"
)

// WebPusher доставляет OS-уведомление через Web Push API (RFC 8030).
// В отличие от Notifier, получатель может быть офлайн.
// Реализация не знает про settingsChannel — фильтрация на уровне диспетчера.
type WebPusher interface {
	PushToUsers(ctx context.Context, userIDs []uuid.UUID, n Notification)
}
