// infrastructure/database/postgres_settings_repository.go
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

// Убеждаемся, что GormSettingsRepository реализует контракт SettingsChannelRepository.
var _ repositories.SettingsChannelRepository = (*GormSettingsRepository)(nil)

// GormSettingsRepository — GORM-реализация SettingsChannelRepository.
type GormSettingsRepository struct {
	db *gorm.DB
}

// NewGormSettingsRepository создаёт репозиторий настроек на основе переданного *gorm.DB.
func NewGormSettingsRepository(db *gorm.DB) *GormSettingsRepository {
	return &GormSettingsRepository{db: db}
}

// Save сохраняет новые настройки канала пользователя.
func (r *GormSettingsRepository) Save(ctx context.Context, settings *domain.SettingsChannel) error {
	if settings == nil {
		return fmt.Errorf("settings repository: save: %w", apperrors.ErrInvalidArgument)
	}

	gormSettings := &models.SettingsChannel{
		UserID:            settings.UserID,
		ChannelID:         settings.ChannelID,
		IsSendPushMessage: settings.IsSendPushMessage,
		CreatedAt:         settings.CreatedAt,
	}

	if err := r.db.WithContext(ctx).Create(gormSettings).Error; err != nil {
		return fmt.Errorf("settings repository: save: %w", err)
	}

	settings.ID = gormSettings.ID
	settings.CreatedAt = gormSettings.CreatedAt
	return nil
}

// FindByID возвращает настройки по идентификатору.
func (r *GormSettingsRepository) FindByID(ctx context.Context, id int) (*domain.SettingsChannel, error) {
	var gormSettings models.SettingsChannel
	if err := r.db.WithContext(ctx).First(&gormSettings, id).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, fmt.Errorf("settings repository: settings %d: %w", id, apperrors.ErrNotFound)
		}
		return nil, fmt.Errorf("settings repository: find by id: %w", err)
	}
	return toDomainSettings(&gormSettings), nil
}

// FindByUserAndChannel возвращает настройки пользователя для конкретного канала.
func (r *GormSettingsRepository) FindByUserAndChannel(ctx context.Context, userID uuid.UUID, channelID int) (*domain.SettingsChannel, error) {
	var gormSettings models.SettingsChannel
	err := r.db.WithContext(ctx).
		Where("user_id = ? AND channel_id = ?", userID, channelID).
		First(&gormSettings).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, fmt.Errorf("settings repository: user %s channel %d: %w", userID, channelID, apperrors.ErrNotFound)
		}
		return nil, fmt.Errorf("settings repository: find by user and channel: %w", err)
	}
	return toDomainSettings(&gormSettings), nil
}

// Update обновляет настройки.
func (r *GormSettingsRepository) Update(ctx context.Context, settings *domain.SettingsChannel) error {
	if settings == nil {
		return fmt.Errorf("settings repository: update: %w", apperrors.ErrInvalidArgument)
	}
	if settings.ID == 0 {
		return fmt.Errorf("settings repository: update: id required: %w", apperrors.ErrInvalidArgument)
	}

	gormSettings := &models.SettingsChannel{
		ID:                settings.ID,
		UserID:            settings.UserID,
		ChannelID:         settings.ChannelID,
		IsSendPushMessage: settings.IsSendPushMessage,
		CreatedAt:         settings.CreatedAt,
	}

	if err := r.db.WithContext(ctx).Save(gormSettings).Error; err != nil {
		return fmt.Errorf("settings repository: update %d: %w", settings.ID, err)
	}
	return nil
}

// Delete удаляет настройки по идентификатору.
func (r *GormSettingsRepository) Delete(ctx context.Context, id int) error {
	if err := r.db.WithContext(ctx).Delete(&models.SettingsChannel{}, id).Error; err != nil {
		return fmt.Errorf("settings repository: delete %d: %w", id, err)
	}
	return nil
}

// FindAllByUserID возвращает все настройки пользователя.
func (r *GormSettingsRepository) FindAllByUserID(ctx context.Context, userID uuid.UUID) ([]*domain.SettingsChannel, error) {
	var gormSettings []models.SettingsChannel
	if err := r.db.WithContext(ctx).
		Where("user_id = ?", userID).
		Order("created_at ASC, id ASC").
		Find(&gormSettings).Error; err != nil {
		return nil, fmt.Errorf("settings repository: find by user %s: %w", userID, err)
	}

	result := make([]*domain.SettingsChannel, len(gormSettings))
	for i := range gormSettings {
		result[i] = toDomainSettings(&gormSettings[i])
	}
	return result, nil
}
