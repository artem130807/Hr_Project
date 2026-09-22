// infrastructure/database/mappers.go
package database

import (
	domain "github.com/yourusername/message-service/internal/domain/entities"
	"github.com/yourusername/message-service/internal/infrastructure/database/models"
)

// toDomainMessage преобразует GORM-модель сообщения в доменную сущность.
func toDomainMessage(m *models.Message) domain.Message {
	return domain.Message{
		ID:         m.ID,
		Content:    m.Content,
		IsRead:     m.IsRead,
		IsSend:     m.IsSend,
		UserId:     m.UserId,
		RoleId:     m.RoleId,
		ChannelID:  m.ChannelID,
		EntityType: m.EntityType,
		EntityID:   m.EntityID,
		CreatedAt:  m.CreatedAt,
	}
}

func toDomainPushSubscription(s *models.PushSubscription) *domain.PushSubscription {
	if s == nil {
		return nil
	}
	return &domain.PushSubscription{
		ID:        s.ID,
		UserID:    s.UserID,
		Endpoint:  s.Endpoint,
		P256dh:    s.P256dh,
		Auth:      s.Auth,
		CreatedAt: s.CreatedAt,
		UpdatedAt: s.UpdatedAt,
	}
}

// toDomainSettings преобразует GORM-модель настроек в доменную сущность.
func toDomainSettings(s *models.SettingsChannel) *domain.SettingsChannel {
	if s == nil {
		return nil
	}
	return &domain.SettingsChannel{
		ID:                s.ID,
		UserID:            s.UserID,
		ChannelID:         s.ChannelID,
		IsSendPushMessage: s.IsSendPushMessage,
		CreatedAt:         s.CreatedAt,
	}
}
