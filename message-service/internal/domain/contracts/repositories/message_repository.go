package repositories

import (
	"context"
	"time"

	"github.com/google/uuid"
	domain "github.com/yourusername/message-service/internal/domain/entities"
)

// MessageQuery — параметры точечного поиска сообщений на уровне домена.
// Все поля опциональны: nil-поля в фильтр не включаются и комбинируются через AND.
// Это доменный контракт, не зависящий от слоя приложения (application-фильтр
// мапится в него в use case).
// Результаты FindByQuery / FindBy*ID (лента) упорядочены от новых к старым.
type MessageQuery struct {
	UserID       *uuid.UUID
	RoleID       *int
	ChannelID    *int
	IsRead       *bool
	IsSend       *bool
	CreatedAfter *time.Time
}

// MessageRepository — контракт доступа к сообщениям.
// Лента уведомлений (FindByQuery / FindByUserID / FindByRoleID / FindByChannelID):
// newest-first. Очередь доставки (FindUnsentByChannelID): oldest-first (FIFO).
type MessageRepository interface {
	Save(ctx context.Context, message *domain.Message) error
	FindByID(ctx context.Context, id int) (*domain.Message, error)
	FindByChannelID(ctx context.Context, channelID int) ([]*domain.Message, error)
	FindByUserID(ctx context.Context, userID uuid.UUID) ([]*domain.Message, error)
	FindNotReadCountByUser(ctx context.Context, userId uuid.UUID, roleId int) (int, error)
	// CountUnreadByChannelIDs — число непрочитанных по каждому channel_id.
	// Каналы без непрочитанных в карту не попадают (считаем 0).
	CountUnreadByChannelIDs(ctx context.Context, channelIDs []int) (map[int]int, error)
	FindByRoleID(ctx context.Context, roleID int) ([]*domain.Message, error)
	FindByQuery(ctx context.Context, q MessageQuery) ([]*domain.Message, error)
	// MarkAsReadByQuery помечает непрочитанные сообщения, попавшие под фильтр,
	// как прочитанные (is_read=true). Возвращает число обновлённых строк.
	// Фильтр аудитории (UserID|RoleID|ChannelID) обязан задать вызывающий слой.
	MarkAsReadByQuery(ctx context.Context, q MessageQuery) (int, error)
	Update(ctx context.Context, message *domain.Message) error
	Delete(ctx context.Context, id int) error
	FindUnsentByChannelID(ctx context.Context, channelID int) ([]*domain.Message, error)
}
