package service

import (
	"context"

	domain "github.com/yourusername/message-service/internal/domain/entities"
)

// NotificationDispatcher резолвит получателей сообщения (channel/user/role +
// mute-настройки канала) и публикует realtime-уведомление через Notifier.
// Вызывать после успешного сохранения сообщения (вне транзакции).
type NotificationDispatcher interface {
	DispatchMessage(ctx context.Context, msg *domain.Message)
}
