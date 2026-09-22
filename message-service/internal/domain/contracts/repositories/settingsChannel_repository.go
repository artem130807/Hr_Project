package repositories

import (
	"context"

	"github.com/google/uuid"
	domain "github.com/yourusername/message-service/internal/domain/entities"
)

// SettingsChannelRepository — контракт доступа к настройкам канала пользователя.
type SettingsChannelRepository interface {
	Save(ctx context.Context, settings *domain.SettingsChannel) error
	FindByID(ctx context.Context, id int) (*domain.SettingsChannel, error)
	FindByUserAndChannel(ctx context.Context, userID uuid.UUID, channelID int) (*domain.SettingsChannel, error)
	Update(ctx context.Context, settings *domain.SettingsChannel) error
	Delete(ctx context.Context, id int) error
	FindAllByUserID(ctx context.Context, userID uuid.UUID) ([]*domain.SettingsChannel, error)
}
