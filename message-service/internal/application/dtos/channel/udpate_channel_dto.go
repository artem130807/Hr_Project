package channel

import "github.com/google/uuid"

// UpdateChannelDto — входной DTO для частичного обновления канала.
// Все поля опциональны (pointer): nil означает «не менять».
type UpdateChannelDto struct {
	Name       *string      `json:"name,omitempty"`
	EntityType *string      `json:"entity_type,omitempty"`
	EntityID   *int         `json:"entity_id,omitempty"`
	UsersIds   *[]uuid.UUID `json:"user_ids,omitempty"`
}
