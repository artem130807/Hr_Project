package database

import (
	"context"
	"fmt"
	"time"

	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
	domain "github.com/yourusername/message-service/internal/domain/entities"
	"github.com/yourusername/message-service/internal/infrastructure/database/models"
	"gorm.io/gorm"
)

var _ repositories.OutboxRepository = (*GormOutboxRepository)(nil)

type GormOutboxRepository struct {
	db *gorm.DB
}

func NewGormOutboxRepository(db *gorm.DB) *GormOutboxRepository {
	return &GormOutboxRepository{db: db}
}

func (r *GormOutboxRepository) Save(ctx context.Context, msg *domain.OutboxMessage) error {
	row := models.OutboxMessage{
		ID:          msg.ID,
		EventType:   msg.EventType,
		Payload:     msg.Payload,
		Status:      msg.Status,
		CreatedAt:   msg.CreatedAt,
		PublishedAt: msg.PublishedAt,
	}
	if err := r.db.WithContext(ctx).Create(&row).Error; err != nil {
		return fmt.Errorf("outbox save: %w", err)
	}
	msg.ID = row.ID
	return nil
}

func (r *GormOutboxRepository) FindPending(ctx context.Context, limit int) ([]*domain.OutboxMessage, error) {
	if limit < 1 {
		limit = 50
	}
	var rows []models.OutboxMessage
	err := r.db.WithContext(ctx).
		Where("status = ?", domain.OutboxStatusPending).
		Order("id ASC").
		Limit(limit).
		Find(&rows).Error
	if err != nil {
		return nil, fmt.Errorf("outbox find pending: %w", err)
	}
	out := make([]*domain.OutboxMessage, 0, len(rows))
	for i := range rows {
		row := rows[i]
		out = append(out, &domain.OutboxMessage{
			ID:          row.ID,
			EventType:   row.EventType,
			Payload:     row.Payload,
			Status:      row.Status,
			CreatedAt:   row.CreatedAt,
			PublishedAt: row.PublishedAt,
		})
	}
	return out, nil
}

func (r *GormOutboxRepository) MarkPublished(ctx context.Context, id int64) error {
	now := time.Now().UTC()
	res := r.db.WithContext(ctx).Model(&models.OutboxMessage{}).
		Where("id = ? AND status = ?", id, domain.OutboxStatusPending).
		Updates(map[string]any{
			"status":       domain.OutboxStatusPublished,
			"published_at": now,
		})
	if res.Error != nil {
		return fmt.Errorf("outbox mark published: %w", res.Error)
	}
	return nil
}
