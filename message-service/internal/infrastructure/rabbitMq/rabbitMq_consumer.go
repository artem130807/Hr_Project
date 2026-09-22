// internal/infrastructure/rabbitMq/rabbitMq_consumer.go
package rabbitmq

import (
	"context"
	"fmt"
	"sync"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"

	messaging "github.com/yourusername/message-service/internal/domain/contracts/messaging"
	"github.com/yourusername/message-service/internal/pkg/config"
)

// Убеждаемся, что Consumer реализует доменный порт messaging.Consumer.
var _ messaging.Consumer = (*Consumer)(nil)

// Consumer — RabbitMQ-реализация messaging.Consumer.
//
// Особенности:
//   - manual ack: сообщение остаётся unacked между Consume и Ack/Nack;
//   - хранится ровно одно pending-сообщение, что сериализует ack/nack
//     и делает consumer безопасным в связке с одним источником (fetchLoop воркера);
//   - Close возвращает pending в очередь и закрывает соединение.
type Consumer struct {
	cfg config.RabbitConfig

	mu         sync.Mutex
	conn       *amqp.Connection
	ch         *amqp.Channel
	deliveries <-chan amqp.Delivery
	pending    *amqp.Delivery
	closed     bool
	done       chan struct{}
}

// NewConsumer подключается к RabbitMQ, объявляет очередь и регистрирует consumer.
func NewConsumer(cfg config.RabbitConfig) (*Consumer, error) {
	c := &Consumer{
		cfg:  cfg,
		done: make(chan struct{}),
	}
	if err := c.connect(); err != nil {
		return nil, err
	}
	return c, nil
}

// connect устанавливает соединение, канал, QoS, очередь и начинает consume.
func (c *Consumer) connect() error {
	conn, err := amqp.DialConfig(c.cfg.URL, amqp.Config{
		Heartbeat: 10 * time.Second,
		Locale:    "en_US",
		Dial:      amqp.DefaultDial(c.cfg.DialTimeout),
	})
	if err != nil {
		return fmt.Errorf("rabbitmq dial: %w", err)
	}

	ch, err := conn.Channel()
	if err != nil {
		_ = conn.Close()
		return fmt.Errorf("rabbitmq channel: %w", err)
	}

	if err := ch.Qos(c.cfg.Prefetch, 0, false); err != nil {
		_ = ch.Close()
		_ = conn.Close()
		return fmt.Errorf("rabbitmq qos: %w", err)
	}

	q, err := ch.QueueDeclare(
		c.cfg.Queue,
		c.cfg.DurableQueue,
		false, // auto-delete
		false, // exclusive
		false, // no-wait
		nil,
	)
	if err != nil {
		_ = ch.Close()
		_ = conn.Close()
		return fmt.Errorf("rabbitmq queue declare: %w", err)
	}

	deliveries, err := ch.Consume(
		q.Name,
		c.cfg.ConsumerTag,
		false, // manual ack
		false, false, false, nil,
	)
	if err != nil {
		_ = ch.Close()
		_ = conn.Close()
		return fmt.Errorf("rabbitmq consume: %w", err)
	}

	c.conn = conn
	c.ch = ch
	c.deliveries = deliveries
	return nil
}

// Consume блокируется до следующего сообщения, отмены ctx или закрытия consumer.
func (c *Consumer) Consume(ctx context.Context) ([]byte, error) {
	c.mu.Lock()
	if c.closed || c.deliveries == nil {
		c.mu.Unlock()
		return nil, messaging.ErrConsumerClosed
	}
	if c.pending != nil {
		c.mu.Unlock()
		return nil, fmt.Errorf("previous message is not acked")
	}
	deliveries := c.deliveries
	done := c.done
	c.mu.Unlock()

	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-done:
		return nil, messaging.ErrConsumerClosed
	case d, ok := <-deliveries:
		if !ok {
			return nil, messaging.ErrConsumerClosed
		}
		if len(d.Body) == 0 {
			_ = d.Nack(false, false) // дропаем «пустое» сообщение без requeue
			return nil, messaging.ErrEmptyMessage
		}

		c.mu.Lock()
		c.pending = &d
		c.mu.Unlock()

		// Возвращаем копию тела, чтобы вызывающий код не зависел от буфера AMQP.
		return append([]byte(nil), d.Body...), nil
	}
}

// Ack подтверждает обработку текущего pending-сообщения.
func (c *Consumer) Ack() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.pending == nil {
		return fmt.Errorf("no pending message to ack")
	}
	err := c.pending.Ack(false)
	c.pending = nil
	if err != nil {
		return fmt.Errorf("rabbitmq ack: %w", err)
	}
	return nil
}

// Nack отрицательно подтверждает текущее pending-сообщение.
func (c *Consumer) Nack(requeue bool) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.pending == nil {
		return fmt.Errorf("no pending message to nack")
	}
	err := c.pending.Nack(false, requeue)
	c.pending = nil
	if err != nil {
		return fmt.Errorf("rabbitmq nack: %w", err)
	}
	return nil
}

// Close останавливает consumer и закрывает channel/connection.
// Идемпотентна. pending возвращается в очередь (requeue).
func (c *Consumer) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return nil
	}
	c.closed = true
	close(c.done)

	if c.pending != nil {
		_ = c.pending.Nack(false, true)
		c.pending = nil
	}

	var firstErr error
	if c.ch != nil {
		if err := c.ch.Cancel(c.cfg.ConsumerTag, false); err != nil && firstErr == nil {
			firstErr = err
		}
		if err := c.ch.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
	}
	if c.conn != nil {
		if err := c.conn.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
	}

	if firstErr != nil {
		return fmt.Errorf("rabbitmq close: %w", firstErr)
	}
	return nil
}

// ErrClosed удобен для внешней проверки (alias на messaging.ErrConsumerClosed).
var ErrClosed = messaging.ErrConsumerClosed
