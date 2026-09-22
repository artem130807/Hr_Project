package service

import (
	"context"

	dto "github.com/yourusername/message-service/internal/application/dtos/message"
	filter "github.com/yourusername/message-service/internal/application/usecases/contracts/filters/message_filters"
)

// MessageService — контракт приложения для работы с сообщениями.
type MessageService interface {
	AddMessage(ctx context.Context, request *dto.CreateMessageDto) (*dto.MessageDto, error)
	RemoveMessage(ctx context.Context, messageID int) error
	EditMessage(ctx context.Context, messageID int, request *dto.UpdateMessageDto) (*dto.MessageDto, error)
	GetMessage(ctx context.Context, messageID int) (*dto.MessageDto, error)
	GetMessagesByFilter(ctx context.Context, f *filter.GetMessagesFilter) ([]*dto.MessageDto, error)
	FindNotReadCountByUser(ctx context.Context) (int, error)
	// MarkMessagesAsRead помечает непрочитанные сообщения выбранной аудитории
	// (личное / роль / канал) как прочитанные. Identity берётся из JWT.
	MarkMessagesAsRead(ctx context.Context, f *filter.GetMessagesFilter) (int, error)
	// MarkMessageAsRead помечает одно сообщение прочитанным, если JWT-пользователь
	// имеет к нему доступ (своё личное / своя роль / участник канала).
	MarkMessageAsRead(ctx context.Context, messageID int) (*dto.MessageDto, error)
}
