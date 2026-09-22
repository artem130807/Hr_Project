package repositories

import (
	"context"

	"github.com/google/uuid"
	domain "github.com/yourusername/message-service/internal/domain/entities"
)

// ChannelRepository — контракт доступа к каналам.
type ChannelRepository interface {
	Save(ctx context.Context, channel *domain.Channel) error
	FindByID(ctx context.Context, id int) (*domain.Channel, error)
	FindByEntity(ctx context.Context, entityType string, entityID int) (*domain.Channel, error)
	FindAllByUserID(ctx context.Context, userID uuid.UUID) ([]*domain.Channel, error)
	// FindAll возвращает все каналы (без сообщений). Используется фоновыми
	// задачами (например, синхронизацией участников), которым нужна вся выборка.
	FindAll(ctx context.Context) ([]*domain.Channel, error)
	Update(ctx context.Context, channel *domain.Channel) error
	Delete(ctx context.Context, id int) error
	AddUserToChannel(ctx context.Context, channelID int, userID uuid.UUID) error
	RemoveUserFromChannel(ctx context.Context, channelID int, userID uuid.UUID) error
	// AddUsers атомарно добавляет список пользователей в канал с дедупликацией
	// на стороне БД. Предпочтительный метод для массовых операций: не затирает
	// поле целиком (как Update), а дополняет массив, что безопасно при
	// конкурентной записи и не требует read-modify-write на стороне приложения.
	AddUsers(ctx context.Context, channelID int, userIDs []uuid.UUID) error
	// RemoveUsers атомарно убирает список пользователей из канала.
	// Используется ACL-синхронизацией (вычистить лишних из закрытого канала).
	RemoveUsers(ctx context.Context, channelID int, userIDs []uuid.UUID) error
	FindByIDs(ctx context.Context, ids []int) ([]*domain.Channel, error)
}
