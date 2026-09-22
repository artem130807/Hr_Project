// infrastructure/database/postgres_message_repository.go
package database

import (
	"context"
	"errors"
	"fmt"

	"github.com/google/uuid"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	"github.com/yourusername/message-service/internal/infrastructure/database/models"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
	"gorm.io/gorm"
)

// Убеждаемся, что GormMessageRepository реализует контракт MessageRepository.
var _ repositories.MessageRepository = (*GormMessageRepository)(nil)

// Inbox / notification feeds: newest first (stable tie-break by id).
const messageFeedOrderDesc = "created_at DESC, id DESC"

// Outbox / send queue: oldest first so delivery stays FIFO.
const messageQueueOrderAsc = "created_at ASC, id ASC"

// GormMessageRepository — GORM-реализация MessageRepository.
type GormMessageRepository struct {
	db *gorm.DB
}

// NewGormMessageRepository создаёт репозиторий сообщений на основе переданного *gorm.DB.
func NewGormMessageRepository(db *gorm.DB) *GormMessageRepository {
	return &GormMessageRepository{db: db}
}

// Save сохраняет новое сообщение и заполняет сгенерированные поля.
func (r *GormMessageRepository) Save(ctx context.Context, message *domain.Message) error {
	if message == nil {
		return fmt.Errorf("message repository: save: %w", apperrors.ErrInvalidArgument)
	}

	gormMessage := &models.Message{
		Content:    message.Content,
		IsRead:     message.IsRead,
		IsSend:     message.IsSend,
		UserId:     message.UserId,
		RoleId:     message.RoleId,
		ChannelID:  message.ChannelID,
		EntityType: message.EntityType,
		EntityID:   message.EntityID,
		CreatedAt:  message.CreatedAt,
	}

	if err := r.db.WithContext(ctx).Create(gormMessage).Error; err != nil {
		return fmt.Errorf("message repository: save: %w", err)
	}

	message.ID = gormMessage.ID
	message.CreatedAt = gormMessage.CreatedAt
	return nil
}

// FindByID возвращает сообщение по идентификатору.
func (r *GormMessageRepository) FindByID(ctx context.Context, id int) (*domain.Message, error) {
	var gormMessage models.Message
	if err := r.db.WithContext(ctx).First(&gormMessage, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, fmt.Errorf("message repository: message %d: %w", id, apperrors.ErrNotFound)
		}
		return nil, fmt.Errorf("message repository: find by id: %w", err)
	}
	msg := toDomainMessage(&gormMessage)
	return &msg, nil
}

// FindByChannelID возвращает сообщения канала (новые сверху — лента уведомлений).
func (r *GormMessageRepository) FindByChannelID(ctx context.Context, channelID int) ([]*domain.Message, error) {
	var gormMessages []models.Message
	if err := r.db.WithContext(ctx).
		Where("channel_id = ?", channelID).
		Order(messageFeedOrderDesc).
		Find(&gormMessages).Error; err != nil {
		return nil, fmt.Errorf("message repository: find by channel %d: %w", channelID, err)
	}
	return toDomainMessages(gormMessages), nil
}

// FindByUserID возвращает личные сообщения пользователя (новые сверху).
func (r *GormMessageRepository) FindByUserID(ctx context.Context, userID uuid.UUID) ([]*domain.Message, error) {
	var gormMessages []models.Message
	if err := r.db.WithContext(ctx).
		Where("user_id = ?", userID).
		Order(messageFeedOrderDesc).
		Find(&gormMessages).Error; err != nil {
		return nil, fmt.Errorf("message repository: find by user %s: %w", userID, err)
	}
	return toDomainMessages(gormMessages), nil
}

// FindByRoleID возвращает ролевые сообщения (новые сверху).
func (r *GormMessageRepository) FindByRoleID(ctx context.Context, roleID int) ([]*domain.Message, error) {
	var gormMessages []models.Message
	if err := r.db.WithContext(ctx).
		Where("role_id = ?", roleID).
		Order(messageFeedOrderDesc).
		Find(&gormMessages).Error; err != nil {
		return nil, fmt.Errorf("message repository: find by role %d: %w", roleID, err)
	}
	return toDomainMessages(gormMessages), nil
}

// FindNotReadCountByUser возвращает число непрочитанных сообщений:
// личных (user_id), ролевых (role_id) или в каналах, где пользователь участник.
func (r *GormMessageRepository) FindNotReadCountByUser(ctx context.Context, userId uuid.UUID, roleId int) (int, error) {
	var count int64
	subQuery := r.db.Model(&models.Channel{}).
		Select("id").
		Where("? = ANY(user_ids)", userId.String())

	err := r.db.WithContext(ctx).
		Model(&models.Message{}).
		Where("is_read = ?", false).
		Where(
			"user_id = ? OR role_id = ? OR channel_id IN (?)",
			userId, roleId, subQuery,
		).
		Count(&count).Error

	if err != nil {
		return 0, fmt.Errorf("failed to count unread messages for user %v: %w", userId, err)
	}

	return int(count), nil
}

// CountUnreadByChannelIDs возвращает {channel_id: число непрочитанных}.
func (r *GormMessageRepository) CountUnreadByChannelIDs(ctx context.Context, channelIDs []int) (map[int]int, error) {
	out := make(map[int]int, len(channelIDs))
	if len(channelIDs) == 0 {
		return out, nil
	}

	type unreadRow struct {
		ChannelID int `gorm:"column:channel_id"`
		Count     int `gorm:"column:unread_count"`
	}
	var rows []unreadRow
	err := r.db.WithContext(ctx).
		Table("messages").
		Select("channel_id, COUNT(*) AS unread_count").
		Where("is_read = ?", false).
		Where("channel_id IN ?", channelIDs).
		Group("channel_id").
		Scan(&rows).Error
	if err != nil {
		return nil, fmt.Errorf("message repository: count unread by channels: %w", err)
	}
	for _, row := range rows {
		out[row.ChannelID] = row.Count
	}
	return out, nil
}

// FindByQuery ищет сообщения по произвольной комбинации фильтров (объединение через AND).
// Поля со значением nil игнорируются. Это позволяет реализации оставаться эффективной
// (фильтрация на стороне БД), не дублируя методы под каждый набор аргументов.
// Порядок: новые сверху — контракт ленты ERP (GET /api/messages).
func (r *GormMessageRepository) FindByQuery(ctx context.Context, q repositories.MessageQuery) ([]*domain.Message, error) {
	var gormMessages []models.Message

	query := r.db.WithContext(ctx).Model(&models.Message{})
	if q.UserID != nil {
		query = query.Where("user_id = ?", *q.UserID)
	}
	if q.RoleID != nil {
		query = query.Where("role_id = ?", *q.RoleID)
	}
	if q.ChannelID != nil {
		query = query.Where("channel_id = ?", *q.ChannelID)
	}
	if q.IsRead != nil {
		query = query.Where("is_read = ?", *q.IsRead)
	}
	if q.IsSend != nil {
		query = query.Where("is_send = ?", *q.IsSend)
	}
	if q.CreatedAfter != nil {
		query = query.Where("created_at >= ?", *q.CreatedAfter)
	}

	if err := query.Order(messageFeedOrderDesc).Find(&gormMessages).Error; err != nil {
		return nil, fmt.Errorf("message repository: find by query: %w", err)
	}
	return toDomainMessages(gormMessages), nil
}

// MarkAsReadByQuery массово ставит is_read=true для непрочитанных сообщений фильтра.
// Требуется хотя бы один критерий аудитории (user_id | role_id | channel_id),
// иначе операция отклоняется — защита от «пометить всё в БД».
func (r *GormMessageRepository) MarkAsReadByQuery(ctx context.Context, q repositories.MessageQuery) (int, error) {
	if q.UserID == nil && q.RoleID == nil && q.ChannelID == nil {
		return 0, fmt.Errorf("message repository: mark as read: audience required: %w", apperrors.ErrInvalidArgument)
	}

	query := r.db.WithContext(ctx).Model(&models.Message{}).Where("is_read = ?", false)
	if q.UserID != nil {
		query = query.Where("user_id = ?", *q.UserID)
	}
	if q.RoleID != nil {
		query = query.Where("role_id = ?", *q.RoleID)
	}
	if q.ChannelID != nil {
		query = query.Where("channel_id = ?", *q.ChannelID)
	}
	if q.IsSend != nil {
		query = query.Where("is_send = ?", *q.IsSend)
	}
	if q.CreatedAfter != nil {
		query = query.Where("created_at >= ?", *q.CreatedAfter)
	}

	res := query.Update("is_read", true)
	if res.Error != nil {
		return 0, fmt.Errorf("message repository: mark as read: %w", res.Error)
	}
	return int(res.RowsAffected), nil
}

// Update обновляет поля сообщения.
func (r *GormMessageRepository) Update(ctx context.Context, message *domain.Message) error {
	if message == nil {
		return fmt.Errorf("message repository: update: %w", apperrors.ErrInvalidArgument)
	}
	if message.ID == 0 {
		return fmt.Errorf("message repository: update: id required: %w", apperrors.ErrInvalidArgument)
	}

	gormMessage := &models.Message{
		ID:         message.ID,
		Content:    message.Content,
		IsRead:     message.IsRead,
		IsSend:     message.IsSend,
		UserId:     message.UserId,
		RoleId:     message.RoleId,
		ChannelID:  message.ChannelID,
		EntityType: message.EntityType,
		EntityID:   message.EntityID,
		CreatedAt:  message.CreatedAt,
	}

	// Save обновляет все поля, включая нулевые (важно для bool-флагов и nullable FK).
	if err := r.db.WithContext(ctx).Save(gormMessage).Error; err != nil {
		return fmt.Errorf("message repository: update %d: %w", message.ID, err)
	}
	return nil
}

// Delete удаляет сообщение по идентификатору.
func (r *GormMessageRepository) Delete(ctx context.Context, id int) error {
	if err := r.db.WithContext(ctx).Delete(&models.Message{}, id).Error; err != nil {
		return fmt.Errorf("message repository: delete %d: %w", id, err)
	}
	return nil
}

// FindUnsentByChannelID возвращает неотправленные сообщения канала (FIFO — старые первыми).
func (r *GormMessageRepository) FindUnsentByChannelID(ctx context.Context, channelID int) ([]*domain.Message, error) {
	var gormMessages []models.Message
	if err := r.db.WithContext(ctx).
		Where("channel_id = ? AND is_send = ?", channelID, false).
		Order(messageQueueOrderAsc).
		Find(&gormMessages).Error; err != nil {
		return nil, fmt.Errorf("message repository: find unsent by channel %d: %w", channelID, err)
	}
	return toDomainMessages(gormMessages), nil
}

// toDomainMessages преобразует слайс GORM-моделей в слайс доменных сущностей.
func toDomainMessages(ms []models.Message) []*domain.Message {
	result := make([]*domain.Message, len(ms))
	for i := range ms {
		msg := toDomainMessage(&ms[i])
		result[i] = &msg
	}
	return result
}
