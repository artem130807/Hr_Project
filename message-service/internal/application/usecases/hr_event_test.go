package usecases

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"
)

func TestHrEventCreated_RecipientUserID(t *testing.T) {
	uid := "11111111-1111-1111-1111-111111111111"

	got, err := (HrEventCreated{UserID: uid}).RecipientUserID()
	if err != nil || got.String() != uid {
		t.Fatalf("user_id: got %v err=%v", got, err)
	}

	got, err = (HrEventCreated{UserIDCamel: uid}).RecipientUserID()
	if err != nil || got.String() != uid {
		t.Fatalf("userId: got %v err=%v", got, err)
	}

	if _, err := (HrEventCreated{}).RecipientUserID(); err == nil {
		t.Fatal("empty user_id must fail")
	}
	if _, err := (HrEventCreated{UserID: "not-a-uuid"}).RecipientUserID(); err == nil {
		t.Fatal("invalid uuid must fail")
	}
	if _, err := (HrEventCreated{UserID: uuid.Nil.String()}).RecipientUserID(); err == nil {
		t.Fatal("nil uuid must fail")
	}
}

func TestHrEventCreated_RenderMessage(t *testing.T) {
	content, err := (HrEventCreated{
		Type:         "birthday",
		EmployeeName: "Иван Иванов",
		EventDate:    "2026-05-01",
		RemindBefore: 3,
		TelegramUser: "@ivan",
		Note:         "торт",
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"Тип события: День рождения",
		"Иван Иванов",
		"01.05.2026",
		"3 дн.",
		"Telegram сотрудника: @ivan",
		"торт",
	} {
		if !strings.Contains(content, want) {
			t.Errorf("content missing %q: %s", want, content)
		}
	}
}

func TestHrEventCreated_RenderAdaptationMessageUsesReadyText(t *testing.T) {
	const note = "Заполните форму руководителя по адаптации: https://hr.example/form"
	content, err := (HrEventCreated{
		Type:         "adaptation_initial",
		EmployeeName: "Кудряшова тестовое",
		EventDate:    "2026-09-10",
		RemindBefore: 0,
		Note:         note,
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	if content != note {
		t.Fatalf("adaptation content must not expose calendar fields: %q", content)
	}
}

func TestHrEventCreated_RenderMessage_PermanentRepeat(t *testing.T) {
	content, err := (HrEventCreated{
		Type:                "permanent",
		EventDate:           "2026-08-24",
		RemindBefore:        0,
		RepeatIntervalCount: 1,
		RepeatIntervalUnit:  "month",
		Note:                "напоминание",
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"Тип события: Постоянное",
		"Повтор: каждый месяц",
		"напоминание",
	} {
		if !strings.Contains(content, want) {
			t.Errorf("content missing %q: %s", want, content)
		}
	}
}

func TestComputeNotifyAt(t *testing.T) {
	got, err := ComputeNotifyAt("2026-05-01", 3, "")
	if err != nil {
		t.Fatal(err)
	}
	want := time.Date(2026, 4, 28, 0, 0, 0, 0, time.UTC)
	if !got.Equal(want) {
		t.Fatalf("got %v want %v", got, want)
	}

	zero, err := ComputeNotifyAt("2026-08-19", 0, "")
	if err != nil {
		t.Fatal(err)
	}
	wantZero := time.Date(2026, 8, 19, 0, 0, 0, 0, time.UTC)
	if !zero.Equal(wantZero) {
		t.Fatalf("remind 0: got %v want %v", zero, wantZero)
	}
}

func TestComputeNotifyAt_SamaraClock(t *testing.T) {
	// 28 Apr 2026 10:30 Samara (UTC+4) → 06:30 UTC
	got, err := ComputeNotifyAt("2026-05-01", 3, "10:30")
	if err != nil {
		t.Fatal(err)
	}
	want := time.Date(2026, 4, 28, 6, 30, 0, 0, time.UTC)
	if !got.Equal(want) {
		t.Fatalf("got %v want %v", got, want)
	}
}

func TestHrEventCreated_RenderMessage_RemindBeforeZero(t *testing.T) {
	content, err := (HrEventCreated{
		Type:         "birthday",
		EmployeeName: "Иван",
		EventDate:    "2026-08-19",
		RemindBefore: 0,
		RemindAtTime: "09:15",
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(content, "Напомнить за: 0 дн.") {
		t.Fatalf("expected remind 0 line, got %s", content)
	}
	if !strings.Contains(content, "Напомнить во сколько: 09:15") {
		t.Fatalf("expected remind time line, got %s", content)
	}
	if strings.Contains(content, "Самара") {
		t.Fatalf("must not include timezone label, got %s", content)
	}
}

func TestHrEventCreated_RenderMessage_OtherExample(t *testing.T) {
	content, err := (HrEventCreated{
		Type:         "other",
		EventDate:    "2026-08-20",
		RemindBefore: 0,
		RemindAtTime: "14:46",
		TelegramUser: "@hr_alt",
		Note:         "тест сообщение",
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	want := strings.Join([]string{
		"Тип события: Другое",
		"Дата: 20.08.2026",
		"Напомнить за: 0 дн.",
		"Напомнить во сколько: 14:46",
		"Telegram сотрудника: @hr_alt",
		"Заметка: тест сообщение",
	}, "\n")
	if content != want {
		t.Fatalf("got:\n%s\nwant:\n%s", content, want)
	}
}

func TestHrEventCreated_RenderMessage_InterviewOmitsEmployee(t *testing.T) {
	content, err := (HrEventCreated{
		Type:         "interview",
		EmployeeName: "Артём Сергеев Валерьевич",
		EventDate:    "2026-08-21",
		RemindBefore: 0,
		RemindAtTime: "12:04",
		TelegramUser: "@hr_alt",
		Note:         "Напоминание о собеседовании: Артём Сергеев Валерьевич",
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	want := strings.Join([]string{
		"Тип события: Собеседование",
		"Дата: 21.08.2026",
		"Напомнить за: 0 дн.",
		"Напомнить во сколько: 12:04",
		"Telegram сотрудника: @hr_alt",
		"Заметка: Напоминание о собеседовании: Артём Сергеев Валерьевич",
	}, "\n")
	if content != want {
		t.Fatalf("got:\n%s\nwant:\n%s", content, want)
	}
	if strings.Contains(content, "Сотрудник:") {
		t.Fatalf("interview must not include employee line, got %s", content)
	}
}

func TestBuildHrEventNotifyPayload(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	body, err := BuildHrEventNotifyPayload(HrEventCreated{
		EventID:      "cccccccc-cccc-cccc-cccc-cccccccccccc",
		OccurredAt:   "2026-08-18T12:00:00Z",
		HrEventID:    55,
		Type:         "birthday",
		EmployeeName: "Иван Иванов",
		TelegramUser: "@ivan_hr",
		EventDate:    "2026-05-01",
		RemindBefore: 3,
		UserID:       uid.String(),
	}, "HR: День рождения\nСотрудник: Иван Иванов", uid)
	if err != nil {
		t.Fatal(err)
	}
	var got HrEventNotify
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	if got.EventType != hrEventNotifyType {
		t.Errorf("event_type=%q", got.EventType)
	}
	if got.NotifyAt != "2026-04-28T00:00:00Z" {
		t.Errorf("notify_at=%q", got.NotifyAt)
	}
	if got.UserID != uid.String() || got.HrEventID != 55 {
		t.Errorf("payload=%+v", got)
	}
}

func TestBuildHrEventNotifyPayload_WithSamaraTime(t *testing.T) {
	uid := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	body, err := BuildHrEventNotifyPayload(HrEventCreated{
		EventID:      "cccccccc-cccc-cccc-cccc-cccccccccccc",
		OccurredAt:   "2026-08-18T12:00:00Z",
		HrEventID:    56,
		Type:         "birthday",
		EventDate:    "2026-08-19",
		RemindBefore: 0,
		RemindAtTime: "15:00",
		UserID:       uid.String(),
	}, "HR: День рождения", uid)
	if err != nil {
		t.Fatal(err)
	}
	var got HrEventNotify
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	// 15:00 Samara = 11:00 UTC
	if got.NotifyAt != "2026-08-19T11:00:00Z" {
		t.Errorf("notify_at=%q want 2026-08-19T11:00:00Z", got.NotifyAt)
	}
	if got.RemindAtTime != "15:00" {
		t.Errorf("remind_at_time=%q", got.RemindAtTime)
	}
}

func TestBuildHrEventNotifyPayload_WithoutUserID(t *testing.T) {
	body, err := BuildHrEventNotifyPayload(HrEventCreated{
		HrEventID:    1,
		Type:         "other",
		EventDate:    "2026-08-19",
		RemindBefore: 0,
		TelegramUser: "@Artem56798",
	}, "HR: Другое", uuid.Nil)
	if err != nil {
		t.Fatal(err)
	}
	var got HrEventNotify
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	if got.UserID != "" {
		t.Errorf("user_id=%q", got.UserID)
	}
	if got.Content == "" || got.NotifyAt != "2026-08-19T00:00:00Z" {
		t.Errorf("payload=%+v", got)
	}
}

func TestHrHiringRequestCreated_RenderMessageUsesText(t *testing.T) {
	content, err := (HrHiringRequestCreated{
		HiringRequestID: 42,
		Text:            "Создана заявка на подбор З-42\nСоздал: Иванов Иван",
		Position:        "ignored",
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	if content != "Создана заявка на подбор З-42\nСоздал: Иванов Иван" {
		t.Errorf("content=%q", content)
	}
}

func TestHrHiringRequestCreated_RenderMessageFallback(t *testing.T) {
	content, err := (HrHiringRequestCreated{
		HiringRequestID: 9,
		Position:        "Логист",
		Department:      "логистический",
		Headcount:       2,
		ActorName:       "Петров Пётр",
	}).RenderMessage()
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"З-9", "Логист", "логистический", "2 чел.", "Петров Пётр"} {
		if !strings.Contains(content, want) {
			t.Errorf("missing %q in %q", want, content)
		}
	}
}

func TestBuildHrHiringRequestNotifyPayload_Immediate(t *testing.T) {
	before := time.Now().UTC().Add(-time.Minute)
	body, err := BuildHrHiringRequestNotifyPayload(HrHiringRequestCreated{
		EventID:         "dddddddd-dddd-dddd-dddd-dddddddddddd",
		OccurredAt:      "2026-09-08T07:00:00Z",
		HiringRequestID: 42,
		Position:        "Логист",
		Department:      "логистический",
		Headcount:       2,
		ActorName:       "Иванов Иван",
	}, "Создана заявка на подбор З-42\nСоздал: Иванов Иван")
	if err != nil {
		t.Fatal(err)
	}
	var got HrEventNotify
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	if got.EventType != hrEventNotifyType || got.Type != hiringRequestNotifyKind {
		t.Errorf("type=%q/%q", got.EventType, got.Type)
	}
	if got.HiringRequestID != 42 || got.ActorName != "Иванов Иван" || got.Position != "Логист" {
		t.Errorf("payload=%+v", got)
	}
	notifyAt, err := time.Parse(time.RFC3339, got.NotifyAt)
	if err != nil {
		t.Fatalf("notify_at parse: %v", err)
	}
	if notifyAt.Before(before) || notifyAt.After(time.Now().UTC().Add(time.Minute)) {
		t.Errorf("notify_at=%s not immediate", got.NotifyAt)
	}
}

func TestParseHrHiringRequestCreated_NullHeadcount(t *testing.T) {
	body := []byte(`{
		"event_type": "hr.hiring_request.created",
		"hiring_request_id": 8,
		"position": "QA",
		"headcount": null,
		"actor_name": "Петров",
		"text": "Создана заявка на подбор З-8"
	}`)
	ev, err := parseHrHiringRequestCreated(body)
	if err != nil {
		t.Fatalf("null headcount must parse: %v", err)
	}
	if ev.HiringRequestID != 8 || int(ev.Headcount) != 0 {
		t.Errorf("parsed=%+v", ev)
	}
	content, err := ev.RenderMessage()
	if err != nil || !strings.Contains(content, "З-8") {
		t.Errorf("render=%q err=%v", content, err)
	}
}
