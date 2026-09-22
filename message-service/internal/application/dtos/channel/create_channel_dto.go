package channel

import "github.com/google/uuid"

// CreateChannelDto — входной DTO для создания канала.
type CreateChannelDto struct {
	Name       string      `json:"name" binding:"required"`
	EntityType string      `json:"entity_type" binding:"required"`
	EntityID   int         `json:"entity_id" binding:"required,min=1"`
	UsersIds   []uuid.UUID `json:"user_ids,omitempty"`
}
