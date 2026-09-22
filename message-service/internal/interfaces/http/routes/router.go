// internal/interfaces/http/routes/router.go
package routes

import (
	"github.com/go-chi/chi/v5"
	"github.com/yourusername/message-service/internal/domain/contracts/auth"
	"github.com/yourusername/message-service/internal/interfaces/http/handlers"
	"github.com/yourusername/message-service/internal/interfaces/http/middleware"
)

// NewRouter создаёт маршрутизатор со всеми эндпоинтами.
func NewRouter(
	messageHandler *handlers.MessageHandler,
	settingsHandler *handlers.SettingsChannelHandler,
	channelHandler *handlers.ChannelHandler,
	wsHandler *handlers.WSHandler,
	pushHandler *handlers.PushHandler,
	authService auth.AuthService,
	internalServiceToken string,
) *chi.Mux {
	r := chi.NewRouter()

	// Внутренние вызовы erp-backend → message-service (без user JWT).
	r.Route("/api/internal", func(r chi.Router) {
		r.Use(middleware.ServiceTokenAuth(internalServiceToken))
		r.Post("/messages", messageHandler.SendMessage)
	})

	r.Route("/api", func(r chi.Router) {
		// WS до JWT middleware chi-группы: токен читается в хендлере (?token= / Bearer).
		if wsHandler != nil {
			r.Get("/ws", wsHandler.Connect)
		}

		r.Group(func(r chi.Router) {
			r.Use(middleware.JWTAuth(authService))

			r.Route("/messages", func(r chi.Router) {
				r.Post("/", messageHandler.SendMessage)
				r.Post("/read", messageHandler.MarkMessagesAsRead)
				r.Get("/unread-count", messageHandler.GetUnreadCount)
				r.Get("/", messageHandler.GetMessagesByFilter)
				r.Get("/{id}", messageHandler.GetMessage)
				r.Put("/{id}", messageHandler.MarkMessageAsRead)
			})

			r.Route("/settings", func(r chi.Router) {
				r.Post("/", settingsHandler.AddSettings)
				r.Get("/user", settingsHandler.GetAllByUser)
				r.Get("/{id}", settingsHandler.GetSettings)
				r.Put("/{id}", settingsHandler.EditSettings)
				r.Delete("/{id}", settingsHandler.RemoveSettings)
			})

			r.Route("/channels", func(r chi.Router) {
				r.Post("/", channelHandler.AddChannel)
				r.Get("/push", channelHandler.GetChannelsByPush)
				r.Get("/{id}", channelHandler.GetChannel)
				r.Put("/{id}", channelHandler.EditChannel)
				r.Delete("/{id}", channelHandler.RemoveChannel)
			})

			if pushHandler != nil {
				r.Route("/push", func(r chi.Router) {
					r.Get("/vapid-public-key", pushHandler.VapidPublicKey)
					r.Post("/subscriptions", pushHandler.Subscribe)
					r.Delete("/subscriptions", pushHandler.Unsubscribe)
				})
			}
		})
	})

	return r
}
