package models

import (
	"database/sql/driver"
	"fmt"
	"strings"

	"github.com/google/uuid"
)

// UUIDs — слайс uuid.UUID, сохраняемый в PostgreSQL-колонке типа uuid[].
// Тип реализует driver.Valuer и sql.Scanner, чтобы GORM корректно
// (де)сериализовал массивы UUID без дополнительных зависимостей.
type UUIDs []uuid.UUID

// Value реализует driver.Valuer: формирует PostgreSQL-литерал массива.
func (u UUIDs) Value() (driver.Value, error) {
	if u == nil {
		return nil, nil
	}
	parts := make([]string, len(u))
	for i, id := range u {
		parts[i] = id.String()
	}
	return fmt.Sprintf("{%s}", strings.Join(parts, ",")), nil
}

// Scan реализует sql.Scanner: разбирает значение, пришедшее из БД.
func (u *UUIDs) Scan(src any) error {
	if src == nil {
		*u = nil
		return nil
	}

	var raw string
	switch v := src.(type) {
	case string:
		raw = v
	case []byte:
		raw = string(v)
	default:
		return fmt.Errorf("models.UUIDs: cannot scan %T", src)
	}

	raw = strings.TrimSpace(raw)
	raw = strings.TrimPrefix(raw, "{")
	raw = strings.TrimSuffix(raw, "}")
	if raw == "" {
		*u = UUIDs{}
		return nil
	}

	parts := strings.Split(raw, ",")
	result := make(UUIDs, len(parts))
	for i, p := range parts {
		id, err := uuid.Parse(strings.TrimSpace(p))
		if err != nil {
			return fmt.Errorf("models.UUIDs: invalid uuid %q: %w", p, err)
		}
		result[i] = id
	}
	*u = result
	return nil
}

// Contains сообщает, входит ли id в массив.
func (u UUIDs) Contains(id uuid.UUID) bool {
	for _, v := range u {
		if v == id {
			return true
		}
	}
	return false
}
