// internal/infrastructure/erp/client.go
//
// HTTP-клиент к erp-backend, реализующий доменный порт providers.UserProvider.
//
// ===========================================================================
// Контракт эндпоинта erp-backend (src/user/v2_router.py → GET /api/v2/users/ids):
// ---------------------------------------------------------------------------
// GET {ERPConfig.BaseURL}/api/v2/users/ids?page={page}&per_page={pageSize}
// Header: X-Service-Token: {ERPConfig.ServiceToken}
//
// Параметры запроса:
//
//	page     — номер страницы, начиная с 1
//	per_page — размер страницы (1..500)
//	active   — (на стороне message-service не передаётся; backend по умолчанию
//	           отдаёт только активных пользователей без superadmin)
//
// Успешный ответ (200 OK):
//
//	{
//	  "items": ["550e8400-e29b-41d4-a716-446655440000", ...],
//	  "users": [{"id": "...", "role_id": 2, "role_name": "Админ"}, ...],
//	  "current_page": 1,
//	  "per_page": 50,
//	  "total_items": 1234,
//	  "total_pages": 25,
//	  "has_more": true
//	}
//
//	items      — массив строковых UUID пользователей текущей страницы
//	users      — те же пользователи с ролью (ACL каналов); может отсутствовать
//	             в старых версиях erp-backend
//	has_more   — true, если есть следующая страница
//
// Ошибки: любой статус, отличный от 200, трактуется как ошибка запроса.
// 403 — неверный/отсутствующий X-Service-Token; 503 — токен не настроен в ERP.
// ===========================================================================
package erp

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/google/uuid"

	providers "github.com/yourusername/message-service/internal/domain/contracts/providers"
	"github.com/yourusername/message-service/internal/pkg/config"
)

// Убеждаемся, что Client реализует доменный порт providers.UserProvider.
var _ providers.UserProvider = (*Client)(nil)

// Client — HTTP-клиент к erp-backend.
type Client struct {
	cfg  config.ERPConfig
	http *http.Client
	// path переопределяем для тестов; по умолчанию "/api/v2/users/ids".
	path string
}

// NewClient создаёт HTTP-клиент к erp-backend.
func NewClient(cfg config.ERPConfig) *Client {
	timeout := cfg.RequestTimeout
	if timeout <= 0 {
		timeout = 10 * time.Second
	}
	return &Client{
		cfg:  cfg,
		http: &http.Client{Timeout: timeout},
		path: "/api/v2/users/ids",
	}
}

// usersIDsResponse — тело ответа erp-backend (GET /api/v2/users/ids).
type usersIDsResponse struct {
	Items       []string        `json:"items"`
	Users       *[]userWithRole `json:"users"`
	CurrentPage int             `json:"current_page"`
	PerPage     int             `json:"per_page"`
	TotalItems  int             `json:"total_items"`
	TotalPages  int             `json:"total_pages"`
	HasMore     bool            `json:"has_more"`
}

type userWithRole struct {
	ID       string `json:"id"`
	RoleID   int    `json:"role_id"`
	RoleName string `json:"role_name"`
}

// GetUserIDs запрашивает страницу списка пользователей у erp-backend.
func (c *Client) GetUserIDs(ctx context.Context, page, pageSize int) (providers.UserPage, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 50
	}

	reqURL, err := c.buildURL(page, pageSize)
	if err != nil {
		return providers.UserPage{}, fmt.Errorf("erp client: build url: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return providers.UserPage{}, fmt.Errorf("erp client: request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	// Аутентификация service-to-service ( MESSAGE_SERVICE_TOKEN в erp-backend ).
	if c.cfg.ServiceToken != "" {
		req.Header.Set("X-Service-Token", c.cfg.ServiceToken)
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return providers.UserPage{}, fmt.Errorf("erp client: do: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return providers.UserPage{}, fmt.Errorf("erp client: unexpected status %d: %s", resp.StatusCode, string(body))
	}

	var payload usersIDsResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return providers.UserPage{}, fmt.Errorf("erp client: decode: %w", err)
	}

	ids, err := parseUUIDs(payload.Items)
	if err != nil {
		return providers.UserPage{}, fmt.Errorf("erp client: parse ids: %w", err)
	}

	pageResolved := payload.CurrentPage
	if pageResolved == 0 {
		pageResolved = page
	}

	out := providers.UserPage{
		UserIDs:  ids,
		Page:     pageResolved,
		Total:    payload.TotalItems,
		HasMore:  payload.HasMore,
		HasRoles: payload.Users != nil,
	}
	if payload.Users != nil {
		refs, err := parseUserRefs(*payload.Users)
		if err != nil {
			return providers.UserPage{}, fmt.Errorf("erp client: parse users: %w", err)
		}
		out.Users = refs
		if len(out.UserIDs) == 0 {
			for _, u := range refs {
				out.UserIDs = append(out.UserIDs, u.ID)
			}
		}
	}

	return out, nil
}

// buildURL собирает URL с query-параметрами пагинации (page, per_page).
func (c *Client) buildURL(page, pageSize int) (string, error) {
	base, err := url.Parse(c.cfg.BaseURL)
	if err != nil {
		return "", fmt.Errorf("parse base url: %w", err)
	}
	base.Path = c.path

	q := base.Query()
	q.Set("page", strconv.Itoa(page))
	q.Set("per_page", strconv.Itoa(pageSize))
	base.RawQuery = q.Encode()
	return base.String(), nil
}

// parseUUIDs преобразует слайс строковых UUID в []uuid.UUID, пропуская пустые.
func parseUUIDs(raw []string) ([]uuid.UUID, error) {
	result := make([]uuid.UUID, 0, len(raw))
	for i, s := range raw {
		if s == "" {
			continue
		}
		id, err := uuid.Parse(s)
		if err != nil {
			return nil, fmt.Errorf("entry #%d %q: %w", i, s, err)
		}
		result = append(result, id)
	}
	return result, nil
}

func parseUserRefs(raw []userWithRole) ([]providers.UserRef, error) {
	result := make([]providers.UserRef, 0, len(raw))
	for i, row := range raw {
		if row.ID == "" {
			continue
		}
		id, err := uuid.Parse(row.ID)
		if err != nil {
			return nil, fmt.Errorf("users[%d] %q: %w", i, row.ID, err)
		}
		result = append(result, providers.UserRef{
			ID:       id,
			RoleID:   row.RoleID,
			RoleName: row.RoleName,
		})
	}
	return result, nil
}
