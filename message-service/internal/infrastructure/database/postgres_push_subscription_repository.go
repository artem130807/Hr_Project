package database

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	"github.com/yourusername/message-service/internal/infrastructure/database/models"
	apperrors "github.com/yourusername/message-service/internal/pkg/errors"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

var _ repositories.PushSubscriptionRepository = (*GormPushSubscriptionRepository)(nil)

type GormPushSubscriptionRepository struct {
	db *gorm.DB
}

func NewGormPushSubscriptionRepository(db *gorm.DB) *GormPushSubscriptionRepository {
	return &GormPushSubscriptionRepository{db: db}
}

func (r *GormPushSubscriptionRepository) Upsert(ctx context.Context, sub *domain.PushSubscription) error {
	if sub == nil {
		return fmt.Errorf("push subscription repository: upsert: %w", apperrors.ErrInvalidArgument)
	}
	row := &models.PushSubscription{
		UserID:   sub.UserID,
		Endpoint: sub.Endpoint,
		P256dh:   sub.P256dh,
		Auth:     sub.Auth,
	}
	err := r.db.WithContext(ctx).
		Clauses(clause.OnConflict{
			Columns:   []clause.Column{{Name: "endpoint"}},
			DoUpdates: clause.AssignmentColumns([]string{"user_id", "p256dh", "auth", "updated_at"}),
		}).
		Create(row).Error
	if err != nil {
		return fmt.Errorf("push subscription repository: upsert: %w", err)
	}
	sub.ID = row.ID
	sub.CreatedAt = row.CreatedAt
	sub.UpdatedAt = row.UpdatedAt
	return nil
}

func (r *GormPushSubscriptionRepository) DeleteByUserAndEndpoint(ctx context.Context, userID uuid.UUID, endpoint string) error {
	res := r.db.WithContext(ctx).
		Where("user_id = ? AND endpoint = ?", userID, endpoint).
		Delete(&models.PushSubscription{})
	if res.Error != nil {
		return fmt.Errorf("push subscription repository: delete by user: %w", res.Error)
	}
	return nil
}

func (r *GormPushSubscriptionRepository) DeleteByEndpoint(ctx context.Context, endpoint string) error {
	res := r.db.WithContext(ctx).
		Where("endpoint = ?", endpoint).
		Delete(&models.PushSubscription{})
	if res.Error != nil {
		return fmt.Errorf("push subscription repository: delete by endpoint: %w", res.Error)
	}
	return nil
}

func (r *GormPushSubscriptionRepository) FindByUserIDs(ctx context.Context, userIDs []uuid.UUID) ([]*domain.PushSubscription, error) {
	if len(userIDs) == 0 {
		return nil, nil
	}
	var rows []models.PushSubscription
	if err := r.db.WithContext(ctx).Where("user_id IN ?", userIDs).Find(&rows).Error; err != nil {
		return nil, fmt.Errorf("push subscription repository: find by users: %w", err)
	}
	out := make([]*domain.PushSubscription, 0, len(rows))
	for i := range rows {
		out = append(out, toDomainPushSubscription(&rows[i]))
	}
	return out, nil
}
