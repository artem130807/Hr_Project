// infrastructure/database/postgres_channel_repository.go
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

// Убеждаемся, что GormChannelRepository реализует контракт ChannelRepository.
var (
	_ repositories.ChannelRepository = (*GormChannelRepository)(nil)
)

// GormChannelRepository — GORM-реализация ChannelRepository.
// Не хранит транзакцию в полях: принимая *gorm.DB в конструкторе,
// корректно работает как с обычным соединением, так и с tx внутри Unit of Work.
type GormChannelRepository struct {
	db *gorm.DB
}

// NewGormChannelRepository создаёт репозиторий каналов на основе переданного *gorm.DB.
func NewGormChannelRepository(db *gorm.DB) *GormChannelRepository {
	return &GormChannelRepository{db: db}
}

// Save сохраняет новый канал и заполняет сгенерированные поля в доменной сущности.
func (r *GormChannelRepository) Save(ctx context.Context, channel *domain.Channel) error {
	if channel == nil {
		return fmt.Errorf("channel repository: save: %w", apperrors.ErrInvalidArgument)
	}

	gormChannel := &models.Channel{
		Name:       channel.Name,
		EntityType: channel.EntityType,
		EntityID:   channel.EntityID,
		UsersIds:   models.UUIDs(channel.UsersIds),
		CreatedAt:  channel.CreatedAt,
	}

	if err := r.db.WithContext(ctx).Create(gormChannel).Error; err != nil {
		return fmt.Errorf("channel repository: save: %w", err)
	}

	channel.ID = gormChannel.ID
	channel.CreatedAt = gormChannel.CreatedAt
	return nil
}

// FindByID возвращает канал по его идентификатору вместе с сообщениями.
func (r *GormChannelRepository) FindByID(ctx context.Context, id int) (*domain.Channel, error) {
	var gormChannel models.Channel
	err := r.db.WithContext(ctx).
		Preload("Messages").
		First(&gormChannel, id).Error
	if err != nil {
		return nil, mapChannelErr(err, id)
	}
	return toDomainChannel(&gormChannel), nil
}

// FindByEntity возвращает канал по паре (entityType, entityID).
func (r *GormChannelRepository) FindByEntity(ctx context.Context, entityType string, entityID int) (*domain.Channel, error) {
	var gormChannel models.Channel
	err := r.db.WithContext(ctx).
		Preload("Messages").
		Where("entity_type = ? AND entity_id = ?", entityType, entityID).
		First(&gormChannel).Error
	if err != nil {
		return nil, mapChannelErr(err, 0)
	}
	return toDomainChannel(&gormChannel), nil
}

// FindAllByUserID возвращает все каналы, в которых участвует пользователь.
func (r *GormChannelRepository) FindAllByUserID(ctx context.Context, userID uuid.UUID) ([]*domain.Channel, error) {
	var gormChannels []models.Channel
	// ? = ANY(user_ids) — PostgreSQL-оператор проверки вхождения в массив.
	if err := r.db.WithContext(ctx).
		Preload("Messages").
		Where("? = ANY(user_ids)", userID.String()).
		Find(&gormChannels).Error; err != nil {
		return nil, fmt.Errorf("channel repository: find by user %s: %w", userID, err)
	}

	domains := make([]*domain.Channel, len(gormChannels))
	for i, gc := range gormChannels {
		domains[i] = toDomainChannel(&gc)
	}
	return domains, nil
}

// FindAll возвращает все каналы без сообщений. Preload Messages намеренно
// опущен: фоновые задачи (синхронизация участников) работают со всеми каналами
// и не нуждаются в загрузке сообщений — это избегает тяжёлых выборок.
func (r *GormChannelRepository) FindAll(ctx context.Context) ([]*domain.Channel, error) {
	var gormChannels []models.Channel
	if err := r.db.WithContext(ctx).
		Order("id ASC").
		Find(&gormChannels).Error; err != nil {
		return nil, fmt.Errorf("channel repository: find all: %w", err)
	}

	domains := make([]*domain.Channel, len(gormChannels))
	for i, gc := range gormChannels {
		domains[i] = toDomainChannel(&gc)
	}
	return domains, nil
}

// Update обновляет поля канала (Name, EntityType, EntityID, UsersIds).
func (r *GormChannelRepository) Update(ctx context.Context, channel *domain.Channel) error {
	if channel == nil {
		return fmt.Errorf("channel repository: update: %w", apperrors.ErrInvalidArgument)
	}
	if channel.ID == 0 {
		return fmt.Errorf("channel repository: update: id required: %w", apperrors.ErrInvalidArgument)
	}

	gormChannel := &models.Channel{
		ID:         channel.ID,
		Name:       channel.Name,
		EntityType: channel.EntityType,
		EntityID:   channel.EntityID,
		UsersIds:   models.UUIDs(channel.UsersIds),
	}

	// Save обновляет все поля, включая нулевые, что важно для массивов и флагов.
	if err := r.db.WithContext(ctx).Save(gormChannel).Error; err != nil {
		return fmt.Errorf("channel repository: update %d: %w", channel.ID, err)
	}
	return nil
}

// Delete удаляет канал по идентификатору.
func (r *GormChannelRepository) Delete(ctx context.Context, id int) error {
	if err := r.db.WithContext(ctx).
		Select("Messages").
		Delete(&models.Channel{}, id).Error; err != nil {
		return fmt.Errorf("channel repository: delete %d: %w", id, err)
	}
	return nil
}

// AddUserToChannel добавляет пользователя в массив user_ids канала (идемпотентно).
func (r *GormChannelRepository) AddUserToChannel(ctx context.Context, channelID int, userID uuid.UUID) error {
	res := r.db.WithContext(ctx).
		Model(&models.Channel{}).
		Where("id = ? AND NOT (? = ANY(user_ids))", channelID, userID.String()).
		Update("user_ids", gorm.Expr("array_append(user_ids, ?)", userID.String()))
	if res.Error != nil {
		return fmt.Errorf("channel repository: add user %s to %d: %w", userID, channelID, res.Error)
	}
	if res.RowsAffected == 0 {
		// Либо канала нет, либо пользователь уже в канале — различаем отдельным запросом.
		var exists bool
		err := r.db.WithContext(ctx).
			Model(&models.Channel{}).
			Select("1").
			Where("id = ?", channelID).
			Limit(1).
			Scan(&exists).Error
		if err != nil {
			return fmt.Errorf("channel repository: check channel %d: %w", channelID, err)
		}
		if !exists {
			return fmt.Errorf("channel repository: add user: channel %d: %w", channelID, apperrors.ErrNotFound)
		}
	}
	return nil
}

// AddUsers атомарно дополняет массив user_ids канала списком пользователей
// с дедупликацией на уровне БД (ARRAY(SELECT DISTINCT unnest(...))).
// В отличие от Update, не затирает строку целиком и не требует
// read-modify-write, поэтому безопасен при конкурентной записи.
// Идемпотентен: повторный вызов с теми же id не создаёт дубликатов.
func (r *GormChannelRepository) AddUsers(ctx context.Context, channelID int, userIDs []uuid.UUID) error {
	if len(userIDs) == 0 {
		return nil
	}
	values := models.UUIDs(userIDs)
	arr, err := values.Value()
	if err != nil {
		return fmt.Errorf("channel repository: add users: encode: %w", err)
	}

	res := r.db.WithContext(ctx).
		Model(&models.Channel{}).
		Where("id = ?", channelID).
		Update("user_ids",
			gorm.Expr("ARRAY(SELECT DISTINCT unnest(user_ids || ?::uuid[]))", arr),
		)
	if res.Error != nil {
		return fmt.Errorf("channel repository: add users to %d: %w", channelID, res.Error)
	}
	if res.RowsAffected == 0 {
		return fmt.Errorf("channel repository: add users: channel %d: %w", channelID, apperrors.ErrNotFound)
	}
	return nil
}

// RemoveUsers атомарно вычитает список UUID из user_ids канала.
func (r *GormChannelRepository) RemoveUsers(ctx context.Context, channelID int, userIDs []uuid.UUID) error {
	if len(userIDs) == 0 {
		return nil
	}
	values := models.UUIDs(userIDs)
	arr, err := values.Value()
	if err != nil {
		return fmt.Errorf("channel repository: remove users: encode: %w", err)
	}

	res := r.db.WithContext(ctx).
		Model(&models.Channel{}).
		Where("id = ?", channelID).
		Update("user_ids",
			gorm.Expr(
				"COALESCE((SELECT array_agg(x) FROM (SELECT unnest(user_ids) AS x EXCEPT SELECT unnest(?::uuid[])) s), '{}'::uuid[])",
				arr,
			),
		)
	if res.Error != nil {
		return fmt.Errorf("channel repository: remove users from %d: %w", channelID, res.Error)
	}
	if res.RowsAffected == 0 {
		return fmt.Errorf("channel repository: remove users: channel %d: %w", channelID, apperrors.ErrNotFound)
	}
	return nil
}

// RemoveUserFromChannel удаляет пользователя из массива user_ids канала.
func (r *GormChannelRepository) RemoveUserFromChannel(ctx context.Context, channelID int, userID uuid.UUID) error {
	res := r.db.WithContext(ctx).
		Model(&models.Channel{}).
		Where("id = ? AND ? = ANY(user_ids)", channelID, userID.String()).
		Update("user_ids", gorm.Expr("array_remove(user_ids, ?)", userID.String()))
	if res.Error != nil {
		return fmt.Errorf("channel repository: remove user %s from %d: %w", userID, channelID, res.Error)
	}
	if res.RowsAffected == 0 {
		var exists bool
		err := r.db.WithContext(ctx).
			Model(&models.Channel{}).
			Select("1").
			Where("id = ?", channelID).
			Limit(1).
			Scan(&exists).Error
		if err != nil {
			return fmt.Errorf("channel repository: check channel %d: %w", channelID, err)
		}
		if !exists {
			return fmt.Errorf("channel repository: remove user: channel %d: %w", channelID, apperrors.ErrNotFound)
		}
		return fmt.Errorf("channel repository: user %s not in channel %d: %w", userID, channelID, apperrors.ErrNotFound)
	}
	return nil
}

// toDomainChannel преобразует GORM-модель в доменную сущность.
func toDomainChannel(gc *models.Channel) *domain.Channel {
	if gc == nil {
		return nil
	}
	messages := make([]domain.Message, len(gc.Messages))
	for i := range gc.Messages {
		messages[i] = toDomainMessage(&gc.Messages[i])
	}

	users := make([]uuid.UUID, len(gc.UsersIds))
	copy(users, []uuid.UUID(gc.UsersIds))

	return &domain.Channel{
		ID:         gc.ID,
		Name:       gc.Name,
		EntityType: gc.EntityType,
		EntityID:   gc.EntityID,
		CreatedAt:  gc.CreatedAt,
		UsersIds:   users,
		Messages:   messages,
	}
}

// mapChannelErr нормализует ошибку GORM в семантическую.
func mapChannelErr(err error, id int) error {
	if errors.Is(err, gorm.ErrRecordNotFound) {
		if id != 0 {
			return fmt.Errorf("channel repository: channel %d: %w", id, apperrors.ErrNotFound)
		}
		return fmt.Errorf("channel repository: channel: %w", apperrors.ErrNotFound)
	}
	return fmt.Errorf("channel repository: query: %w", err)
}
func (r *GormChannelRepository) FindByIDs(ctx context.Context, ids []int) ([]*domain.Channel, error) {
	if len(ids) == 0 {
		return []*domain.Channel{}, nil
	}

	var gormChannels []models.Channel
	if err := r.db.WithContext(ctx).
		Where("id IN ?", ids).
		Find(&gormChannels).Error; err != nil {
		return nil, fmt.Errorf("failed to find channels by ids: %w", err)
	}

	domains := make([]*domain.Channel, len(gormChannels))
	for i, gc := range gormChannels {
		domains[i] = toDomainChannel(&gc)
	}
	return domains, nil
}
