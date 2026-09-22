package auth

import (
	"context"

	"github.com/google/uuid"
)

// ContextAuth извлекает identity текущего пользователя из request context.
type ContextAuth interface {
	GetUserID(ctx context.Context) (uuid.UUID, error)
	GetRoleID(ctx context.Context) (int, error)
}
