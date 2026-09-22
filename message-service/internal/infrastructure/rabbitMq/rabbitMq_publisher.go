// internal/infrastructure/rabbitMq/rabbitMq_publisher.go
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

var _ messaging.Publisher = (*Publisher)(nil)

// Publisher публикует сообщения в durable-очередь (default exchange + routing_key=queue).
type Publisher struct {
	cfg   config.RabbitConfig
	queue string

	mu     sync.Mutex
	conn   *amqp.Connection
	ch     *amqp.Channel
	closed bool
}

// NewPublisher подключается к RabbitMQ и объявляет очередь публикации.
func NewPublisher(cfg config.RabbitConfig, queue string) (*Publisher, error) {
	if queue == "" {
		return nil, fmt.Errorf("rabbitmq publisher: empty queue")
	}
	p := &Publisher{cfg: cfg, queue: queue}
	if err := p.connect(); err != nil {
		return nil, err
	}
	return p, nil
}

func (p *Publisher) connect() error {
	conn, err := amqp.DialConfig(p.cfg.URL, amqp.Config{
		Heartbeat: 10 * time.Second,
		Locale:    "en_US",
		Dial:      amqp.DefaultDial(p.cfg.DialTimeout),
	})
	if err != nil {
		return fmt.Errorf("rabbitmq publisher dial: %w", err)
	}
	ch, err := conn.Channel()
	if err != nil {
		_ = conn.Close()
		return fmt.Errorf("rabbitmq publisher channel: %w", err)
	}
	_, err = ch.QueueDeclare(
		p.queue,
		p.cfg.DurableQueue,
		false, false, false, nil,
	)
	if err != nil {
		_ = ch.Close()
		_ = conn.Close()
		return fmt.Errorf("rabbitmq publisher queue declare: %w", err)
	}
	p.conn = conn
	p.ch = ch
	return nil
}

func (p *Publisher) Publish(ctx context.Context, body []byte) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed || p.ch == nil {
		return fmt.Errorf("rabbitmq publisher: closed")
	}
	if len(body) == 0 {
		return fmt.Errorf("rabbitmq publisher: empty body")
	}
	return p.ch.PublishWithContext(
		ctx,
		"",
		p.queue,
		false,
		false,
		amqp.Publishing{
			ContentType:  "application/json",
			DeliveryMode: amqp.Persistent,
			Timestamp:    time.Now().UTC(),
			Body:         body,
			Headers:      amqp.Table{"event_type": "hr.event.notify"},
		},
	)
}

func (p *Publisher) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return nil
	}
	p.closed = true
	var first error
	if p.ch != nil {
		if err := p.ch.Close(); err != nil && first == nil {
			first = err
		}
	}
	if p.conn != nil {
		if err := p.conn.Close(); err != nil && first == nil {
			first = err
		}
	}
	return first
}
