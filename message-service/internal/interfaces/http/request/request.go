package request

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
	filter "github.com/yourusername/message-service/internal/application/usecases/contracts/filters/message_filters"
)

func DecodeJSON(r *http.Request, v interface{}) error {
	return json.NewDecoder(r.Body).Decode(v)
}

func DecodeAndValidate(r *http.Request, v interface{}) error {
	return json.NewDecoder(r.Body).Decode(v)
}

func IDFromPath(r *http.Request, key string) (int, error) {
	idStr := chi.URLParam(r, key)
	if idStr == "" {
		return 0, fmt.Errorf("missing %s", key)
	}
	id, err := strconv.Atoi(idStr)
	if err != nil {
		return 0, fmt.Errorf("invalid %s: %w", key, err)
	}
	return id, nil
}

// MessagesFilterFromQuery разбирает GET /messages?user_id=&role_id=&channel_id=&is_read=
func MessagesFilterFromQuery(r *http.Request) (*filter.GetMessagesFilter, error) {
	q := r.URL.Query()
	f := &filter.GetMessagesFilter{}

	if v := q.Get("user_id"); v != "" {
		id, err := uuid.Parse(v)
		if err != nil {
			return nil, fmt.Errorf("invalid user_id: %w", err)
		}
		f.UserId = &id
	}
	if v := q.Get("role_id"); v != "" {
		id, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("invalid role_id: %w", err)
		}
		f.RoleId = &id
	}
	if v := q.Get("channel_id"); v != "" {
		id, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("invalid channel_id: %w", err)
		}
		f.ChannelId = &id
	}
	if v := q.Get("is_read"); v != "" {
		b, err := strconv.ParseBool(v)
		if err != nil {
			return nil, fmt.Errorf("invalid is_read: %w", err)
		}
		f.IsRead = &b
	}
	if v := q.Get("created_after"); v != "" {
		t, err := time.Parse(time.RFC3339, v)
		if err != nil {
			return nil, fmt.Errorf("invalid created_after: %w", err)
		}
		f.CreatedAt = &t
	}

	return f, nil
}
