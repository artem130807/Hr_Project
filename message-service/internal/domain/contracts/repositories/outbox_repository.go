package repositories

import (
	"context"

	domain "github.com/yourusername/message-service/internal/domain/entities"
)

// OutboxRepository — хранилище transactional outbox.
type OutboxRepository interface {
	Save(ctx context.Context, msg *domain.OutboxMessage) error
	FindPending(ctx context.Context, limit int) ([]*domain.OutboxMessage, error)
	MarkPublished(ctx context.Context, id int64) error
}
