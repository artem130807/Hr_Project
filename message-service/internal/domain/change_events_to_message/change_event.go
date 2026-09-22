package change_events_to_message

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type ChangeEvent struct {
	EventType   string
	CarId       int
	ExecutorId  int
	CompanyName string
	ActorUserId uuid.UUID
	Changed     ChangedProperty
	OccuredAt   time.Time
}

func (e *ChangeEvent) DeserializeToChangeEvent(data []byte) (ChangeEvent, error) {
	var evt ChangeEvent
	err := json.Unmarshal(data, &evt)
	return evt, err
}
