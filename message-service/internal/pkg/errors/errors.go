// internal/pkg/errors/errors.go
package errors

import (
	"errors"
	"net/http"
)

type AppError struct {
	Code     string // машинный код (например, "VALIDATION_ERROR")
	Message  string // человеческое сообщение
	HTTPCode int    // HTTP-статус (400, 404, 500 и т.д.)
	Err      error  // вложенная ошибка (опционально)
}

// Реализация интерфейса error
func (e *AppError) Error() string {
	if e.Err != nil {
		return e.Message + ": " + e.Err.Error()
	}
	return e.Message
}

// Фабричные функции для удобства создания ошибок
func NewNotFound(message string) *AppError {
	return &AppError{
		Code:     "NOT_FOUND",
		Message:  message,
		HTTPCode: http.StatusNotFound,
	}
}

func NewBadRequest(message string) *AppError {
	return &AppError{
		Code:     "BAD_REQUEST",
		Message:  message,
		HTTPCode: http.StatusBadRequest,
	}
}
func NewErrInvalidArgument(message string) *AppError {
	return &AppError{
		Code:     "ErrInvalidArgument",
		Message:  message,
		HTTPCode: http.StatusBadRequest,
	}
}
func NewConflict(message string) *AppError {
	return &AppError{
		Code:     "CONFLICT",
		Message:  message,
		HTTPCode: http.StatusConflict,
	}
}

func NewInternalError(message string) *AppError {
	return &AppError{
		Code:     "INTERNAL_ERROR",
		Message:  message,
		HTTPCode: http.StatusInternalServerError,
	}
}
func NewUnauthorized(message string) *AppError {
	return &AppError{
		Code:     "UNAUTHORIZED",
		Message:  message,
		HTTPCode: http.StatusUnauthorized,
	}
}

// Доменно-независимые семантические ошибки приложения.
// Используются репозиториями (обёрнутыми через fmt.Errorf) и сервисами,
// чтобы вышележащим слоям (HTTP/gRPC) не приходилось парсить текст ошибок.
var (
	// ErrNotFound — запрашиваемая сущность не найдена.
	ErrNotFound = errors.New("запрашиваемая сущность не найдена")

	// ErrAlreadyExists — нарушение уникальности / дубликат.
	ErrAlreadyExists = errors.New("нарушение уникальности")

	// ErrInvalidArgument — некорректные входные данные запроса.
	ErrInvalidArgument = errors.New("некорректные входные данные")
)
