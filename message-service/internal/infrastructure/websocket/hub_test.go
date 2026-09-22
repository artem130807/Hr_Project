package websocket

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"
	gowebsocket "github.com/gorilla/websocket"
	"github.com/yourusername/message-service/internal/domain/contracts/realtime"
)

func dialWS(t *testing.T, url string) *gowebsocket.Conn {
	t.Helper()
	c, _, err := gowebsocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		t.Fatalf("dial %s: %v", url, err)
	}
	return c
}

func readNotification(t *testing.T, c *gowebsocket.Conn, timeout time.Duration) realtime.Notification {
	t.Helper()
	_ = c.SetReadDeadline(time.Now().Add(timeout))
	_, raw, err := c.ReadMessage()
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	var got realtime.Notification
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	return got
}

func TestHub_NotifyUsersAndRole(t *testing.T) {
	hub := NewHub(nil)
	done := make(chan struct{})
	go func() {
		hub.Run()
		close(done)
	}()
	t.Cleanup(func() {
		hub.Close()
		select {
		case <-done:
		case <-time.After(2 * time.Second):
			t.Error("hub.Run did not stop")
		}
	})

	u1 := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	u2 := uuid.MustParse("22222222-2222-2222-2222-222222222222")

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasSuffix(r.URL.Path, "/u1"):
			hub.ServeWS(w, r, u1, 1)
		case strings.HasSuffix(r.URL.Path, "/u2"):
			hub.ServeWS(w, r, u2, 2)
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)

	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http")
	c1 := dialWS(t, wsURL+"/u1")
	t.Cleanup(func() { _ = c1.Close() })
	c2 := dialWS(t, wsURL+"/u2")
	t.Cleanup(func() { _ = c2.Close() })

	deadline := time.Now().Add(2 * time.Second)
	for hub.OnlineUserCount() < 2 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if hub.OnlineUserCount() < 2 {
		t.Fatalf("expected 2 online users, got %d", hub.OnlineUserCount())
	}

	u2Ch := make(chan realtime.Notification, 1)
	go func() {
		_ = c2.SetReadDeadline(time.Now().Add(3 * time.Second))
		_, raw, err := c2.ReadMessage()
		if err != nil {
			return
		}
		var got realtime.Notification
		if json.Unmarshal(raw, &got) == nil {
			u2Ch <- got
		}
	}()

	hub.NotifyUsers(context.Background(), []uuid.UUID{u1}, realtime.Notification{
		Type: "notification", ID: 7, Content: "hi",
	})
	got := readNotification(t, c1, 2*time.Second)
	if got.ID != 7 || got.Content != "hi" {
		t.Fatalf("user notify got %+v", got)
	}

	select {
	case unexpected := <-u2Ch:
		t.Fatalf("u2 should not receive user-targeted msg, got %+v", unexpected)
	case <-time.After(150 * time.Millisecond):
	}

	hub.NotifyRole(context.Background(), 2, realtime.Notification{
		Type: "notification", ID: 8, Content: "role",
	})
	select {
	case got2 := <-u2Ch:
		if got2.ID != 8 {
			t.Fatalf("role payload %+v", got2)
		}
	case <-time.After(2 * time.Second):
		// reader may have exited after idle; read synchronously
		got2 := readNotification(t, c2, 2*time.Second)
		if got2.ID != 8 {
			t.Fatalf("role payload %+v", got2)
		}
	}
}
