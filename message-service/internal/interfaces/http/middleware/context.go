package middleware

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/yourusername/message-service/internal/application/usecases/contracts/auth"
)

type ContextAuthImpl struct{}

func NewContextAuth() auth.ContextAuth {
	return &ContextAuthImpl{}
}

func (c *ContextAuthImpl) GetUserID(ctx context.Context) (uuid.UUID, error) {
	userID, ok := ctx.Value(UserIDKey).(uuid.UUID)
	if !ok || userID == uuid.Nil {
		return uuid.Nil, fmt.Errorf("user ID not found in context")
	}
	return userID, nil
}

func (c *ContextAuthImpl) GetRoleID(ctx context.Context) (int, error) {
	roleID, ok := ctx.Value(UserRoleIDKey).(int)
	if !ok || roleID <= 0 {
		return 0, fmt.Errorf("user role_id not found in context")
	}
	return roleID, nil
}
