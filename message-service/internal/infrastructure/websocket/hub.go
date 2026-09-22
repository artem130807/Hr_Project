// Package websocket — инфраструктурный realtime-транспорт на gorilla/websocket.
package websocket

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"sync"
	"time"

	"github.com/google/uuid"
	gowebsocket "github.com/gorilla/websocket"
	"github.com/yourusername/message-service/internal/domain/contracts/realtime"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 512
	sendBuffer     = 32
)

var _ realtime.Notifier = (*Hub)(nil)

// Hub хранит активные WebSocket-подключения и реализует realtime.Notifier.
type Hub struct {
	mu         sync.RWMutex
	byUser     map[uuid.UUID]map[*Client]struct{}
	register   chan *Client
	unregister chan *Client
	done       chan struct{}
	log        *slog.Logger
	upgrader   gowebsocket.Upgrader
}

// Client — одно WS-соединение аутентифицированного пользователя.
type Client struct {
	hub       *Hub
	conn      *gowebsocket.Conn
	send      chan []byte
	userID    uuid.UUID
	roleID    int
	closeOnce sync.Once
}

func (c *Client) closeSend() {
	c.closeOnce.Do(func() { close(c.send) })
}

// NewHub создаёт hub. log == nil → slog.Default().
func NewHub(log *slog.Logger) *Hub {
	if log == nil {
		log = slog.Default()
	}
	return &Hub{
		byUser:     make(map[uuid.UUID]map[*Client]struct{}),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		done:       make(chan struct{}),
		log:        log.With("component", "ws_hub"),
		upgrader: gowebsocket.Upgrader{
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
			// Авторизация — по JWT; Origin проверяется на уровне gateway/proxy.
			CheckOrigin: func(r *http.Request) bool { return true },
		},
	}
}

// Run крутит цикл регистрации/отписки до Close().
func (h *Hub) Run() {
	defer h.closeAll()
	for {
		select {
		case <-h.done:
			return
		case c := <-h.register:
			h.addClient(c)
		case c := <-h.unregister:
			h.removeClient(c)
		}
	}
}

// Close останавливает Run (клиенты закрываются в defer Run).
func (h *Hub) Close() {
	select {
	case <-h.done:
		return
	default:
		close(h.done)
	}
}

func (h *Hub) closeAll() {
	h.mu.Lock()
	defer h.mu.Unlock()
	for _, clients := range h.byUser {
		for c := range clients {
			c.closeSend()
			_ = c.conn.Close()
		}
	}
	h.byUser = make(map[uuid.UUID]map[*Client]struct{})
}

func (h *Hub) addClient(c *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	set, ok := h.byUser[c.userID]
	if !ok {
		set = make(map[*Client]struct{})
		h.byUser[c.userID] = set
	}
	set[c] = struct{}{}
	h.log.Debug("client registered", "user_id", c.userID, "role_id", c.roleID, "conns", len(set))
}

func (h *Hub) removeClient(c *Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	set, ok := h.byUser[c.userID]
	if !ok {
		return
	}
	if _, exists := set[c]; !exists {
		return
	}
	delete(set, c)
	c.closeSend()
	_ = c.conn.Close()
	if len(set) == 0 {
		delete(h.byUser, c.userID)
	}
	h.log.Debug("client unregistered", "user_id", c.userID, "role_id", c.roleID)
}

// ServeWS апгрейдит HTTP → WebSocket и запускает read/write pumps.
func (h *Hub) ServeWS(w http.ResponseWriter, r *http.Request, userID uuid.UUID, roleID int) {
	conn, err := h.upgrader.Upgrade(w, r, nil)
	if err != nil {
		h.log.Warn("upgrade failed", "err", err)
		return
	}
	client := &Client{
		hub:    h,
		conn:   conn,
		send:   make(chan []byte, sendBuffer),
		userID: userID,
		roleID: roleID,
	}
	select {
	case <-h.done:
		_ = conn.Close()
		return
	case h.register <- client:
	}
	go client.writePump()
	go client.readPump()
}

// NotifyUsers реализует realtime.Notifier.
func (h *Hub) NotifyUsers(_ context.Context, userIDs []uuid.UUID, n realtime.Notification) {
	if len(userIDs) == 0 {
		return
	}
	payload, err := json.Marshal(n)
	if err != nil {
		h.log.Error("marshal notification", "err", err)
		return
	}
	seen := make(map[uuid.UUID]struct{}, len(userIDs))
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, id := range userIDs {
		if _, dup := seen[id]; dup {
			continue
		}
		seen[id] = struct{}{}
		for c := range h.byUser[id] {
			h.enqueue(c, payload)
		}
	}
}

// NotifyRole реализует realtime.Notifier.
func (h *Hub) NotifyRole(_ context.Context, roleID int, n realtime.Notification) {
	if roleID <= 0 {
		return
	}
	payload, err := json.Marshal(n)
	if err != nil {
		h.log.Error("marshal notification", "err", err)
		return
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, clients := range h.byUser {
		for c := range clients {
			if c.roleID == roleID {
				h.enqueue(c, payload)
			}
		}
	}
}

func (h *Hub) enqueue(c *Client, payload []byte) {
	select {
	case c.send <- payload:
	default:
		// Медленный клиент — дропаем, чтобы не блокировать hub.
		h.log.Warn("drop notification: slow client", "user_id", c.userID)
	}
}

// OnlineUserCount — для тестов/метрик.
func (h *Hub) OnlineUserCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.byUser)
}

func (c *Client) readPump() {
	defer func() {
		select {
		case <-c.hub.done:
		case c.hub.unregister <- c:
		}
	}()
	c.conn.SetReadLimit(maxMessageSize)
	_ = c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		return c.conn.SetReadDeadline(time.Now().Add(pongWait))
	})
	for {
		if _, _, err := c.conn.ReadMessage(); err != nil {
			return
		}
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		_ = c.conn.Close()
	}()
	for {
		select {
		case msg, ok := <-c.send:
			_ = c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				_ = c.conn.WriteMessage(gowebsocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(gowebsocket.TextMessage, msg); err != nil {
				return
			}
		case <-ticker.C:
			_ = c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(gowebsocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}
