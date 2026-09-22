package response

import (
	"encoding/json"
	stdErrors "errors"
	"net/http"

	"github.com/yourusername/message-service/internal/pkg/errors"
)

func JSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func Error(w http.ResponseWriter, err error) {
	var appErr *errors.AppError
	if stdErrors.As(err, &appErr) {
		http.Error(w, appErr.Message, appErr.HTTPCode)
		return
	}
	http.Error(w, "Internal server error", http.StatusInternalServerError)
}
