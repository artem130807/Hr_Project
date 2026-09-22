package service

import (
	"context"

	"github.com/google/uuid"
	dto "github.com/yourusername/message-service/internal/application/dtos/settings"
)

// SettingsChannelService — контракт приложения для работы с настройками канала.
// Identity текущего пользователя извлекается из context внутри реализации.
type SettingsChannelService interface {
	AddSettings(ctx context.Context, request *dto.CreateSettingsDto) (*dto.SettingsDto, error)
	RemoveSettings(ctx context.Context, id int) error
	EditSettings(ctx context.Context, id int, request *dto.UpdateSettingsDto) (*dto.SettingsDto, error)
	GetSettings(ctx context.Context, id int) (*dto.SettingsDto, error)
	GetAllByUser(ctx context.Context) ([]*dto.SettingsDto, error)
	FindByUserAndChannel(ctx context.Context, userID uuid.UUID, channelId int) (*dto.SettingsDto, error)
}
