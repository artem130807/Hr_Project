package messaging

import "context"

// Publisher — доменный порт публикации сообщений в брокер.
// Инфраструктура (RabbitMQ) реализует этот интерфейс.
type Publisher interface {
	Publish(ctx context.Context, body []byte) error
	Close() error
}
