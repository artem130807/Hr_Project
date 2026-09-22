// internal/domain/contracts/messaging/consumer.go
package messaging

import (
	"context"
	"errors"
)

// Consumer — доменный порт потребителя сообщений из брокера.
// Инфраструктура (RabbitMQ, Kafka и т.п.) реализует этот интерфейс,
// а прикладной слой зависит только от абстракции.
//
// Контракт намеренно синхронный и «одно сообщение за раз»:
// Consume блокируется до появления сообщения, после чего оно остаётся
// неподтверждённым, пока не будет вызван Ack или Nack. Это гарантирует
// сериализацию ack/nack на одном потребителе и совместимо с at-least-once.
type Consumer interface {
	// Consume блокируется до получения сообщения, отмены ctx
	// или закрытия потребителя. Возвращает тело сообщения.
	Consume(ctx context.Context) ([]byte, error)
	// Ack подтверждает обработку текущего (последнего Consumed) сообщения.
	Ack() error
	// Nack отрицательно подтверждает сообщение; requeue=true вернёт его в очередь.
	Nack(requeue bool) error
	// Close корректно останавливает потребитель: возвращает pending в очередь
	// и закрывает channel/connection. Безопасен для повторного вызова.
	Close() error
}

// Семантические ошибки потребителя.
var (
	// ErrConsumerClosed — потребитель закрыт (Close или разрыв соединения).
	ErrConsumerClosed = errors.New("consumer closed")
	// ErrEmptyMessage — получено сообщение с пустым телом.
	ErrEmptyMessage = errors.New("empty message")
)
