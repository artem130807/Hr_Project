// internal/application/usecases/hr_event.go
package usecases

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
)

const hrEventCreatedType = "hr.event.created"
const hrHiringRequestCreatedType = "hr.hiring_request.created"
const hrEventNotifyType = "hr.event.notify"
const hiringRequestNotifyKind = "hiring_request"

// samaraTZ — Europe/Samara (UTC+4, Moscow+1). Fixed offset keeps CI/containers without tzdata.
var samaraTZ = time.FixedZone("Europe/Samara", 4*3600)

// HrEventCreated — контракт JSON события hr.event.created.
type HrEventCreated struct {
	EventID             string `json:"event_id"`
	EventType           string `json:"event_type"`
	OccurredAt          string `json:"occurred_at"`
	HrEventID           int    `json:"hr_event_id"`
	Type                string `json:"type"`
	EmployeeName        string `json:"employee_name"`
	ChildName           string `json:"child_name"`
	TelegramUser        string `json:"telegram_user"`
	Note                string `json:"note"`
	EventDate           string `json:"event_date"`
	RemindBefore        int    `json:"remind_before"`
	RemindAtTime        string `json:"remind_at_time"` // optional "HH:MM" Samara local
	IsDone              bool   `json:"is_done"`
	RepeatIntervalCount int    `json:"repeat_interval_count"`
	RepeatIntervalUnit  string `json:"repeat_interval_unit"`
	Occurrence          string `json:"occurrence"`
	UserID              string `json:"user_id"`
	UserIDCamel         string `json:"userId"`
	ActorUserID         string `json:"actor_user_id"`
}

func parseHrEventCreated(body []byte) (HrEventCreated, error) {
	var ev HrEventCreated
	err := json.Unmarshal(body, &ev)
	return ev, err
}

// RecipientUserID возвращает UUID получателя (user_id / userId).
func (e HrEventCreated) RecipientUserID() (uuid.UUID, error) {
	raw := strings.TrimSpace(e.UserID)
	if raw == "" {
		raw = strings.TrimSpace(e.UserIDCamel)
	}
	if raw == "" {
		return uuid.Nil, fmt.Errorf("hr_event: empty user_id")
	}
	id, err := uuid.Parse(raw)
	if err != nil {
		return uuid.Nil, fmt.Errorf("hr_event: invalid user_id: %w", err)
	}
	if id == uuid.Nil {
		return uuid.Nil, fmt.Errorf("hr_event: nil user_id")
	}
	return id, nil
}

var hrEventTypeLabels = map[string]string{
	"birthday":         "День рождения",
	"child_birthday":   "День рождения ребёнка",
	"work_anniversary": "Годовщина работы",
	"interview":        "Собеседование",
	"permanent":        "Постоянное",
	"other":            "Другое",
}

func (e HrEventCreated) typeLabel() string {
	if l, ok := hrEventTypeLabels[strings.TrimSpace(e.Type)]; ok {
		return l
	}
	if t := strings.TrimSpace(e.Type); t != "" {
		return t
	}
	return "Событие"
}

func formatRepeatInterval(count int, unit string) string {
	unit = strings.TrimSpace(strings.ToLower(unit))
	if unit == "" {
		return ""
	}
	if count < 1 {
		count = 1
	}
	switch unit {
	case "day":
		if count == 1 {
			return "каждый день"
		}
		return fmt.Sprintf("каждые %d дн.", count)
	case "week":
		if count == 1 {
			return "каждую неделю"
		}
		return fmt.Sprintf("каждые %d нед.", count)
	case "month":
		if count == 1 {
			return "каждый месяц"
		}
		return fmt.Sprintf("каждые %d мес.", count)
	case "year":
		if count == 1 {
			return "каждый год"
		}
		return fmt.Sprintf("каждые %d г.", count)
	default:
		return unit
	}
}

func formatEventDate(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	if len(raw) >= 10 {
		raw = raw[:10]
	}
	day, err := time.Parse("2006-01-02", raw)
	if err != nil {
		return strings.TrimSpace(raw)
	}
	return day.Format("02.01.2006")
}

// RenderMessage строит текст личного уведомления по HR-событию.
func (e HrEventCreated) RenderMessage() (string, error) {
	// Adaptation already provides a recipient-ready text in Note. Rendering it
	// as a generic calendar event exposed internal type names and service fields.
	if strings.HasPrefix(strings.TrimSpace(e.Type), "adaptation_") {
		content := strings.TrimSpace(e.Note)
		if content == "" {
			return "", fmt.Errorf("hr_event: empty adaptation content")
		}
		return content, nil
	}
	var b strings.Builder
	fmt.Fprintf(&b, "Тип события: %s", e.typeLabel())
	isInterview := strings.EqualFold(strings.TrimSpace(e.Type), "interview")
	if name := strings.TrimSpace(e.EmployeeName); name != "" && !isInterview {
		fmt.Fprintf(&b, "\nСотрудник: %s", name)
	}
	if child := strings.TrimSpace(e.ChildName); child != "" {
		fmt.Fprintf(&b, "\nРебёнок: %s", child)
	}
	if date := formatEventDate(e.EventDate); date != "" {
		fmt.Fprintf(&b, "\nДата: %s", date)
	}
	if e.RemindBefore >= 0 {
		fmt.Fprintf(&b, "\nНапомнить за: %d дн.", e.RemindBefore)
	}
	if t := strings.TrimSpace(e.RemindAtTime); t != "" {
		fmt.Fprintf(&b, "\nНапомнить во сколько: %s", t)
	}
	if tg := strings.TrimSpace(e.TelegramUser); tg != "" {
		fmt.Fprintf(&b, "\nTelegram сотрудника: %s", tg)
	}
	if repeat := formatRepeatInterval(e.RepeatIntervalCount, e.RepeatIntervalUnit); repeat != "" {
		fmt.Fprintf(&b, "\nПовтор: %s", repeat)
	}
	if note := strings.TrimSpace(e.Note); note != "" {
		fmt.Fprintf(&b, "\nЗаметка: %s", note)
	}
	content := strings.TrimSpace(b.String())
	if content == "" {
		return "", fmt.Errorf("hr_event: empty content")
	}
	return content, nil
}

func parseClockHHMM(raw string) (hour, min int, err error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return 0, 0, fmt.Errorf("empty time")
	}
	parts := strings.Split(raw, ":")
	if len(parts) < 2 || len(parts) > 3 {
		return 0, 0, fmt.Errorf("invalid time %q", raw)
	}
	hour, err = strconv.Atoi(parts[0])
	if err != nil || hour < 0 || hour > 23 {
		return 0, 0, fmt.Errorf("invalid hour in %q", raw)
	}
	min, err = strconv.Atoi(parts[1])
	if err != nil || min < 0 || min > 59 {
		return 0, 0, fmt.Errorf("invalid minute in %q", raw)
	}
	return hour, min, nil
}

// ComputeNotifyAt = (event_date − remind_before) at optional Samara clock time.
//
//   - remindAtTime empty → 00:00 UTC on that calendar day (send as soon as day is due)
//   - remindAtTime set → HH:MM in Europe/Samara (UTC+4), returned as UTC instant
func ComputeNotifyAt(eventDate string, remindBefore int, remindAtTime string) (time.Time, error) {
	raw := strings.TrimSpace(eventDate)
	if raw == "" {
		return time.Time{}, fmt.Errorf("hr_event: empty event_date")
	}
	if len(raw) >= 10 {
		raw = raw[:10]
	}
	day, err := time.ParseInLocation("2006-01-02", raw, time.UTC)
	if err != nil {
		return time.Time{}, fmt.Errorf("hr_event: invalid event_date: %w", err)
	}
	if remindBefore < 0 {
		remindBefore = 0
	}
	day = day.AddDate(0, 0, -remindBefore)

	clock := strings.TrimSpace(remindAtTime)
	if clock == "" {
		return time.Date(day.Year(), day.Month(), day.Day(), 0, 0, 0, 0, time.UTC), nil
	}
	hour, minute, err := parseClockHHMM(clock)
	if err != nil {
		return time.Time{}, fmt.Errorf("hr_event: invalid remind_at_time: %w", err)
	}
	local := time.Date(day.Year(), day.Month(), day.Day(), hour, minute, 0, 0, samaraTZ)
	return local.UTC(), nil
}

// HrEventNotify — payload очереди hr.event.notify (для opened-monitor-bot).
type HrEventNotify struct {
	EventID         string `json:"event_id"`
	EventType       string `json:"event_type"`
	OccurredAt      string `json:"occurred_at"`
	HrEventID       int    `json:"hr_event_id"`
	Type            string `json:"type"`
	EmployeeName    string `json:"employee_name,omitempty"`
	ChildName       string `json:"child_name,omitempty"`
	TelegramUser    string `json:"telegram_user,omitempty"`
	Note            string `json:"note,omitempty"`
	EventDate       string `json:"event_date"`
	RemindBefore    int    `json:"remind_before"`
	RemindAtTime    string `json:"remind_at_time,omitempty"`
	NotifyAt        string `json:"notify_at"`
	UserID          string `json:"user_id"`
	Content         string `json:"content"`
	HiringRequestID int    `json:"hiring_request_id,omitempty"`
	ActorName       string `json:"actor_name,omitempty"`
	Position        string `json:"position,omitempty"`
	Department      string `json:"department,omitempty"`
	Headcount       int    `json:"headcount,omitempty"`
}

// BuildHrEventNotifyPayload собирает JSON для outbox / hr.event.notify.
func BuildHrEventNotifyPayload(ev HrEventCreated, content string, userID uuid.UUID) ([]byte, error) {
	notifyAt, err := ComputeNotifyAt(ev.EventDate, ev.RemindBefore, ev.RemindAtTime)
	if err != nil {
		return nil, err
	}
	occurred := strings.TrimSpace(ev.OccurredAt)
	if occurred == "" {
		occurred = time.Now().UTC().Format(time.RFC3339)
	}
	eventID := strings.TrimSpace(ev.EventID)
	if eventID == "" {
		eventID = uuid.NewString()
	}
	payload := HrEventNotify{
		EventID:      eventID,
		EventType:    hrEventNotifyType,
		OccurredAt:   occurred,
		HrEventID:    ev.HrEventID,
		Type:         ev.Type,
		EmployeeName: strings.TrimSpace(ev.EmployeeName),
		ChildName:    strings.TrimSpace(ev.ChildName),
		TelegramUser: strings.TrimSpace(ev.TelegramUser),
		Note:         strings.TrimSpace(ev.Note),
		EventDate:    strings.TrimSpace(ev.EventDate),
		RemindBefore: ev.RemindBefore,
		RemindAtTime: strings.TrimSpace(ev.RemindAtTime),
		NotifyAt:     notifyAt.UTC().Format(time.RFC3339),
		UserID:       "",
		Content:      content,
	}
	if userID != uuid.Nil {
		payload.UserID = userID.String()
	}
	return json.Marshal(payload)
}

// HrHiringRequestCreated — контракт JSON hr.hiring_request.created (HR → message-service).
type HrHiringRequestCreated struct {
	EventID         string      `json:"event_id"`
	EventType       string      `json:"event_type"`
	OccurredAt      string      `json:"occurred_at"`
	HiringRequestID int         `json:"hiring_request_id"`
	Position        string      `json:"position"`
	Department      string      `json:"department"`
	Headcount       optionalInt `json:"headcount"`
	Urgency         string      `json:"urgency"`
	InitiatorName   string      `json:"initiator_name"`
	ManagerName     string      `json:"manager_name"`
	ActorUserID     string      `json:"actor_user_id"`
	ActorName       string      `json:"actor_name"`
	Text            string      `json:"text"`
}

func parseHrHiringRequestCreated(body []byte) (HrHiringRequestCreated, error) {
	var ev HrHiringRequestCreated
	err := json.Unmarshal(body, &ev)
	return ev, err
}

// optionalInt принимает JSON number, null и "".
type optionalInt int

func (o *optionalInt) UnmarshalJSON(b []byte) error {
	s := strings.TrimSpace(string(b))
	if s == "" || s == "null" || s == `""` {
		*o = 0
		return nil
	}
	var n int
	if err := json.Unmarshal(b, &n); err != nil {
		return err
	}
	*o = optionalInt(n)
	return nil
}

func (e HrHiringRequestCreated) RenderMessage() (string, error) {
	if text := strings.TrimSpace(e.Text); text != "" {
		return text, nil
	}
	var b strings.Builder
	fmt.Fprintf(&b, "Создана заявка на подбор")
	if e.HiringRequestID > 0 {
		fmt.Fprintf(&b, " З-%d", e.HiringRequestID)
	}
	if p := strings.TrimSpace(e.Position); p != "" {
		fmt.Fprintf(&b, "\nДолжность: %s", p)
	}
	if d := strings.TrimSpace(e.Department); d != "" {
		fmt.Fprintf(&b, "\nОтдел: %s", d)
	}
	if e.Headcount > 0 {
		fmt.Fprintf(&b, "\nНужно: %d чел.", int(e.Headcount))
	}
	if n := strings.TrimSpace(e.InitiatorName); n != "" {
		fmt.Fprintf(&b, "\nИнициатор: %s", n)
	}
	if n := strings.TrimSpace(e.ActorName); n != "" {
		fmt.Fprintf(&b, "\nСоздал: %s", n)
	}
	content := strings.TrimSpace(b.String())
	if content == "" {
		return "", fmt.Errorf("hr_hiring_request: empty content")
	}
	return content, nil
}

// BuildHrHiringRequestNotifyPayload — hr.event.notify с notify_at=сейчас (без откладки).
func BuildHrHiringRequestNotifyPayload(ev HrHiringRequestCreated, content string) ([]byte, error) {
	occurred := strings.TrimSpace(ev.OccurredAt)
	if occurred == "" {
		occurred = time.Now().UTC().Format(time.RFC3339)
	}
	eventID := strings.TrimSpace(ev.EventID)
	if eventID == "" {
		eventID = uuid.NewString()
	}
	now := time.Now().UTC().Format(time.RFC3339)
	payload := HrEventNotify{
		EventID:         eventID,
		EventType:       hrEventNotifyType,
		OccurredAt:      occurred,
		HrEventID:       ev.HiringRequestID,
		Type:            hiringRequestNotifyKind,
		Note:            strings.TrimSpace(ev.Urgency),
		NotifyAt:        now,
		Content:         content,
		HiringRequestID: ev.HiringRequestID,
		ActorName:       strings.TrimSpace(ev.ActorName),
		Position:        strings.TrimSpace(ev.Position),
		Department:      strings.TrimSpace(ev.Department),
		Headcount:       int(ev.Headcount),
	}
	return json.Marshal(payload)
}

// BuildAdaptationTalkHRNotifyPayload создаёт немедленный Telegram-сигнал HR.
func BuildAdaptationTalkHRNotifyPayload(ev ChangeEvent, content string) ([]byte, error) {
	occurred := strings.TrimSpace(ev.OccurredAt)
	if occurred == "" {
		occurred = time.Now().UTC().Format(time.RFC3339)
	}
	eventID := strings.TrimSpace(ev.EventID)
	if eventID == "" {
		eventID = uuid.NewString()
	}
	notifyType := strings.TrimSpace(ev.NotificationType)
	if notifyType == "" {
		notifyType = "adaptation_talk_hr"
	}
	payload := HrEventNotify{
		EventID:    eventID,
		EventType:  hrEventNotifyType,
		OccurredAt: occurred,
		HrEventID:  ev.EntityID,
		Type:       notifyType,
		NotifyAt:   time.Now().UTC().Format(time.RFC3339),
		Content:    strings.TrimSpace(content),
	}
	return json.Marshal(payload)
}

func formatOptionalUserID(id uuid.UUID, err error) string {
	if err != nil || id == uuid.Nil {
		return ""
	}
	return id.String()
}

func peekEventType(body []byte) (string, error) {
	var env struct {
		EventType string `json:"event_type"`
	}
	if err := json.Unmarshal(body, &env); err != nil {
		return "", err
	}
	return strings.TrimSpace(env.EventType), nil
}
