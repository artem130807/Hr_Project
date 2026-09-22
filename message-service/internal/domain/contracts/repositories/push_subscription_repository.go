package repositories

import (
	"context"

	"github.com/google/uuid"
	domain "github.com/yourusername/message-service/internal/domain/entities"
)

// PushSubscriptionRepository хранит Web Push подписки отдельно от UoW сообщений:
// отправка идёт после коммита, 410 от push-сервиса удаляет строку вне транзакции сообщения.
type PushSubscriptionRepository interface {
	Upsert(ctx context.Context, sub *domain.PushSubscription) error
	DeleteByUserAndEndpoint(ctx context.Context, userID uuid.UUID, endpoint string) error
	DeleteByEndpoint(ctx context.Context, endpoint string) error
	FindByUserIDs(ctx context.Context, userIDs []uuid.UUID) ([]*domain.PushSubscription, error)
}
