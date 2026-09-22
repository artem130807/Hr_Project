package domain

import "time"

const (
	OutboxStatusPending   = "pending"
	OutboxStatusPublished = "published"
)

// OutboxMessage — запись transactional outbox для надёжной публикации в брокер.
type OutboxMessage struct {
	ID          int64
	EventType   string
	Payload     []byte
	Status      string
	CreatedAt   time.Time
	PublishedAt *time.Time
}

// NewPendingOutbox создаёт pending-запись outbox.
func NewPendingOutbox(eventType string, payload []byte) (*OutboxMessage, error) {
	if eventType == "" {
		return nil, ErrOutboxEmptyEventType
	}
	if len(payload) == 0 {
		return nil, ErrOutboxEmptyPayload
	}
	return &OutboxMessage{
		EventType: eventType,
		Payload:   append([]byte(nil), payload...),
		Status:    OutboxStatusPending,
		CreatedAt: time.Now().UTC(),
	}, nil
}

var (
	ErrOutboxEmptyEventType = errString("outbox: empty event_type")
	ErrOutboxEmptyPayload   = errString("outbox: empty payload")
)

type errString string

func (e errString) Error() string { return string(e) }
