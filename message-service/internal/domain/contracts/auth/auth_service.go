package auth

import (
	"context"

	"github.com/google/uuid"
)

// AuthService — контракт для работы с аутентификацией.
type AuthService interface {
	// GetUserIDFromToken извлекает userID из JWT-токена.
	GetUserIDFromToken(ctx context.Context, token string) (uuid.UUID, error)

	// GetRoleIDFromToken извлекает role_id из JWT-токена.
	GetRoleIDFromToken(ctx context.Context, token string) (int, error)

	// ValidateToken проверяет валидность токена.
	ValidateToken(ctx context.Context, token string) error

	// ExtractClaims извлекает все claims из токена.
	ExtractClaims(ctx context.Context, token string) (*Claims, error)
}

// Claims — структура с данными из JWT.
type Claims struct {
	UserID uuid.UUID `json:"user_id"`
	RoleID int       `json:"role_id"`
}
