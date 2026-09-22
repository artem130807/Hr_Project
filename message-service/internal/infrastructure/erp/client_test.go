// internal/infrastructure/erp/client_test.go
package erp

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/yourusername/message-service/internal/pkg/config"
)

// TestGetUserIDs_Contract проверяет, что клиент обращается к реальному эндпоинту
// erp-backend: путь /api/v2/users/ids, query per_page, заголовок X-Service-Token
// и корректно разбирает форму ответа {items,current_page,per_page,total_items,total_pages,has_more}.
func TestGetUserIDs_Contract(t *testing.T) {
	id1 := uuid.New()
	id2 := uuid.New()

	var gotPath, gotPerPage, gotPage, gotToken string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotPerPage = r.URL.Query().Get("per_page")
		gotPage = r.URL.Query().Get("page")
		gotToken = r.Header.Get("X-Service-Token")

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":        []string{id1.String(), id2.String()},
			"current_page": 1,
			"per_page":     50,
			"total_items":  123,
			"total_pages":  3,
			"has_more":     true,
		})
	}))
	defer srv.Close()

	c := NewClient(config.ERPConfig{
		BaseURL:        srv.URL,
		RequestTimeout: 2 * time.Second,
		ServiceToken:   "test-service-token",
	})

	page, err := c.GetUserIDs(context.Background(), 1, 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if gotPath != "/api/v2/users/ids" {
		t.Errorf("path = %q, want /api/v2/users/ids", gotPath)
	}
	if gotPerPage != "50" {
		t.Errorf("per_page = %q, want 50", gotPerPage)
	}
	if gotPage != "1" {
		t.Errorf("page = %q, want 1", gotPage)
	}
	if gotToken != "test-service-token" {
		t.Errorf("X-Service-Token = %q, want test-service-token", gotToken)
	}
	if len(page.UserIDs) != 2 || page.UserIDs[0] != id1 || page.UserIDs[1] != id2 {
		t.Errorf("UserIDs = %v, want [%s %s]", page.UserIDs, id1, id2)
	}
	if !page.HasMore {
		t.Errorf("HasMore = false, want true")
	}
	if page.Total != 123 {
		t.Errorf("Total = %d, want 123", page.Total)
	}
	if page.Page != 1 {
		t.Errorf("Page = %d, want 1", page.Page)
	}
}

func TestGetUserIDs_ParsesUsersAndRoles(t *testing.T) {
	id1 := uuid.New()
	id2 := uuid.New()

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items": []string{id1.String(), id2.String()},
			"users": []map[string]any{
				{"id": id1.String(), "role_id": 2, "role_name": "Админ"},
				{"id": id2.String(), "role_id": 3, "role_name": "Менеджер"},
			},
			"current_page": 1,
			"per_page":     50,
			"total_items":  2,
			"total_pages":  1,
			"has_more":     false,
		})
	}))
	defer srv.Close()

	c := NewClient(config.ERPConfig{BaseURL: srv.URL, ServiceToken: "x"})
	page, err := c.GetUserIDs(context.Background(), 1, 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !page.HasRoles {
		t.Fatal("HasRoles = false, want true")
	}
	if len(page.Users) != 2 {
		t.Fatalf("Users = %d, want 2", len(page.Users))
	}
	if page.Users[0].ID != id1 || page.Users[0].RoleName != "Админ" || page.Users[0].RoleID != 2 {
		t.Errorf("user[0] = %+v", page.Users[0])
	}
	if page.Users[1].RoleName != "Менеджер" {
		t.Errorf("user[1].RoleName = %q", page.Users[1].RoleName)
	}
}

func TestGetUserIDs_MissingUsersFieldHasNoRoles(t *testing.T) {
	id := uuid.New()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":        []string{id.String()},
			"current_page": 1,
			"per_page":     50,
			"total_items":  1,
			"total_pages":  1,
			"has_more":     false,
		})
	}))
	defer srv.Close()

	c := NewClient(config.ERPConfig{BaseURL: srv.URL, ServiceToken: "x"})
	page, err := c.GetUserIDs(context.Background(), 1, 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if page.HasRoles {
		t.Fatal("HasRoles = true, want false when users omitted")
	}
	if len(page.Users) != 0 {
		t.Errorf("Users = %v, want empty", page.Users)
	}
}

// TestGetUserIDs_Non200 проверяет обработку ошибочного статуса (например 403).
func TestGetUserIDs_Non200(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte("invalid token"))
	}))
	defer srv.Close()

	c := NewClient(config.ERPConfig{BaseURL: srv.URL, ServiceToken: "x"})
	if _, err := c.GetUserIDs(context.Background(), 1, 50); err == nil {
		t.Fatal("expected error on 403, got nil")
	} else if !strings.Contains(err.Error(), "403") {
		t.Errorf("error should mention status 403, got: %v", err)
	}
}

// TestGetUserIDs_EmptyItems проверяет пустую страницу.
func TestGetUserIDs_EmptyItems(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"items":        []string{},
			"current_page": 5,
			"per_page":     50,
			"total_items":  0,
			"total_pages":  1,
			"has_more":     false,
		})
	}))
	defer srv.Close()

	c := NewClient(config.ERPConfig{BaseURL: srv.URL, ServiceToken: "x"})
	page, err := c.GetUserIDs(context.Background(), 5, 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(page.UserIDs) != 0 {
		t.Errorf("UserIDs = %v, want empty", page.UserIDs)
	}
	if page.HasMore {
		t.Errorf("HasMore = true, want false")
	}
}
