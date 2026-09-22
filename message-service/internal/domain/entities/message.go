// domain/message.go
package domain

import (
	"errors"
	"strings"
	"time"

	"github.com/google/uuid"
)

// Message — уведомление, связанное с каналом / пользователем / ролью.
type Message struct {
	ID         int
	Content    string     // текст уведомления
	UserId     *uuid.UUID // привязка к конкретному пользователю
	RoleId     *int       // привязка к роли
	ChannelID  *int       // привязка к каналу
	EntityType *string    // опционально: trip | executor | car | driver | trailer
	EntityID   *int       // PK сущности для deep-link на клиенте
	IsRead     bool
	IsSend     bool
	CreatedAt  time.Time
}

// WithEntity прикрепляет ссылку на сущность (идемпотентно; пустые значения игнорируются).
func (m *Message) WithEntity(entityType string, entityID int) *Message {
	if m == nil {
		return nil
	}
	et := strings.ToLower(strings.TrimSpace(entityType))
	if et == "" || entityID <= 0 {
		return m
	}
	m.EntityType = &et
	id := entityID
	m.EntityID = &id
	return m
}

// NewMessage создаёт новое сообщение.
func SendMessageToChannel(content string, channelID int) (*Message, error) {
	if content == "" {
		return nil, errors.New("Сообщение не может быть пустым")
	}
	if channelID <= 0 {
		return nil, errors.New("Неправильное айди канала")
	}
	return &Message{
		Content:   content,
		IsRead:    false,
		IsSend:    false,
		ChannelID: &channelID,
		CreatedAt: time.Now().UTC(),
	}, nil
}
func SendMessageToUser(content string, userId uuid.UUID) (*Message, error) {
	if content == "" {
		return nil, errors.New("Сообщение не может быть пустым")
	}
	if userId == uuid.Nil {
		return nil, errors.New("Неправильное айди канала")
	}
	return &Message{
		Content:   content,
		IsRead:    false,
		IsSend:    false,
		UserId:    &userId,
		CreatedAt: time.Now().UTC(),
	}, nil
}
func SendMessageToRole(content string, roleId int) (*Message, error) {
	if content == "" {
		return nil, errors.New("Сообщение не может быть пустым")
	}
	if roleId <= 0 {
		return nil, errors.New("Неправильное айди канала")
	}
	return &Message{
		Content:   content,
		IsRead:    false,
		IsSend:    false,
		RoleId:    &roleId,
		CreatedAt: time.Now().UTC(),
	}, nil
}

// MarkAsSent помечает сообщение как отправленное.
func (m *Message) MarkAsSent() {
	m.IsSend = true
}
func (m *Message) MarkAsRead() {
	m.IsRead = true
}

// UpdateContent обновляет содержимое (только если ещё не отправлено).
func (m *Message) UpdateContent(newContent string) error {
	if m.IsSend {
		return errors.New("Сообщение уже отправлено")
	}
	if newContent == "" {
		return errors.New("Контент не может быть пустым")
	}
	m.Content = newContent
	return nil
}
