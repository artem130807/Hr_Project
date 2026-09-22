package domain

import (
	"errors"
	"time"

	"github.com/google/uuid"
)

// Channel — канал для отправки сообщений, связанных с определённой сущностью.
type Channel struct {
	ID         int
	Name       string // название канала
	EntityType string // тип сущности: "car", "order", "user" и т.д.
	EntityID   int    // идентификатор сущности
	CreatedAt  time.Time
	UsersIds   []uuid.UUID // айди участников канала
	Messages   []Message   // сообщения канала
}

// NewChannel создаёт канал для конкретной сущности.
func NewChannel(name string, entityType string, entityID int) (*Channel, error) {
	if entityType == "" {
		return nil, errors.New("Тип модели не может быть пустым")
	}
	if entityID <= 0 {
		return nil, errors.New("Айди модели не может быть меньше нуля")
	}
	return &Channel{
		Name:       name,
		EntityType: entityType,
		EntityID:   entityID,
		CreatedAt:  time.Now().UTC(),
		UsersIds:   []uuid.UUID{},
		Messages:   []Message{},
	}, nil
}

// AddUser добавляет пользователя в канал.
func (c *Channel) AddUser(user uuid.UUID) error {
	for _, u := range c.UsersIds {
		if u == user {
			return errors.New("пользователь уже есть в канале")
		}
	}
	c.UsersIds = append(c.UsersIds, user)
	return nil
}

// RemoveUser удаляет пользователя из канала.
func (c *Channel) RemoveUser(userID uuid.UUID) error {
	for i, u := range c.UsersIds {
		if u == userID {
			c.UsersIds = append(c.UsersIds[:i], c.UsersIds[i+1:]...)
			return nil
		}
	}
	return errors.New("пользователя нету в канале")
}

// AddMessage добавляет сообщение в канал (используется при создании).
func (c *Channel) AddMessage(msg Message) {
	c.Messages = append(c.Messages, msg)
}
