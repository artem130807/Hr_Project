package auth

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/yourusername/message-service/internal/domain/contracts/auth"
	"github.com/yourusername/message-service/internal/pkg/config"
)

// JWTClaims — сырые claims токена.
// RoleID — основной числовой идентификатор роли.
// Role — legacy-поле (число как string/number), используется как fallback.
type JWTClaims struct {
	UserID uuid.UUID    `json:"user_id"`
	RoleID int          `json:"role_id"`
	Role   flexibleRole `json:"role"`
	jwt.RegisteredClaims
}

// flexibleRole принимает role_id из legacy-claim "role" (int или numeric string).
type flexibleRole struct {
	raw int
	ok  bool
}

func (r *flexibleRole) UnmarshalJSON(data []byte) error {
	if string(data) == "null" {
		return nil
	}
	var asInt int
	if err := json.Unmarshal(data, &asInt); err == nil {
		r.raw = asInt
		r.ok = true
		return nil
	}
	var asString string
	if err := json.Unmarshal(data, &asString); err == nil {
		n, err := strconv.Atoi(asString)
		if err != nil {
			// объект {name, permissions} и прочий non-numeric legacy — игнорируем
			return nil
		}
		r.raw = n
		r.ok = true
		return nil
	}
	return nil
}

type JWTService struct {
	secret string
}

func NewJWTService(cfg *config.AppConfig) auth.AuthService {
	return &JWTService{
		secret: cfg.JWTSecret,
	}
}

func (s *JWTService) ValidateToken(ctx context.Context, tokenString string) error {
	_, err := s.parseToken(tokenString)
	return err
}

func (s *JWTService) GetUserIDFromToken(ctx context.Context, tokenString string) (uuid.UUID, error) {
	claims, err := s.ExtractClaims(ctx, tokenString)
	if err != nil {
		return uuid.Nil, err
	}
	return claims.UserID, nil
}

func (s *JWTService) GetRoleIDFromToken(ctx context.Context, tokenString string) (int, error) {
	claims, err := s.ExtractClaims(ctx, tokenString)
	if err != nil {
		return 0, err
	}
	return claims.RoleID, nil
}

func (s *JWTService) ExtractClaims(ctx context.Context, tokenString string) (*auth.Claims, error) {
	token, err := s.parseToken(tokenString)
	if err != nil {
		return nil, err
	}

	claims, ok := token.Claims.(*JWTClaims)
	if !ok || !token.Valid {
		return nil, errors.New("invalid token claims")
	}

	if claims.UserID == uuid.Nil {
		return nil, errors.New("user_id missing in token")
	}

	roleID := claims.RoleID
	if roleID <= 0 && claims.Role.ok {
		roleID = claims.Role.raw
	}
	if roleID <= 0 {
		return nil, errors.New("role_id missing in token")
	}

	return &auth.Claims{
		UserID: claims.UserID,
		RoleID: roleID,
	}, nil
}

func (s *JWTService) parseToken(tokenString string) (*jwt.Token, error) {
	return jwt.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(s.secret), nil
	})
}
