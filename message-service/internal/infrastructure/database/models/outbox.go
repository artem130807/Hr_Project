package models

import "time"

// OutboxMessage — GORM-модель transactional outbox.
type OutboxMessage struct {
	ID          int64      `gorm:"primaryKey"`
	EventType   string     `gorm:"column:event_type;size:120;not null;index"`
	Payload     []byte     `gorm:"column:payload;type:jsonb;not null"`
	Status      string     `gorm:"column:status;size:32;not null;index"`
	CreatedAt   time.Time  `gorm:"column:created_at;autoCreateTime"`
	PublishedAt *time.Time `gorm:"column:published_at"`
}

func (OutboxMessage) TableName() string {
	return "outbox_messages"
}
