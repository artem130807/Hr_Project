package usecases

import (
	"fmt"
	"strings"
	"testing"
)

// Полный payload message.car.changed (с company_name и actor_user_id).
func sampleCarChangedBody() []byte {
	return []byte(`{
		"event_id": "11111111-1111-1111-1111-111111111111",
		"event_type": "message.car.changed",
		"occurred_at": "2026-08-06T12:00:00+00:00",
		"car_id": 42,
		"tms_id": "22222222-2222-2222-2222-222222222222",
		"executor_id": 7,
		"company_name": "ООО Ромашка",
		"actor_user_id": "33333333-3333-3333-3333-333333333333",
		"changed": {
			"vin": {"old": "OLDVIN", "new": "NEWVIN"},
			"ownership_type_name": {"old": "1 - Собственность", "new": "6 - Привлеченный"}
		}
	}`)
}

func TestDeserializeToChangeEvent_Car(t *testing.T) {
	ce, err := DeserializeToChangeEvent(sampleCarChangedBody())
	if err != nil {
		t.Fatalf("deserialize: %v", err)
	}
	if ce.EventType != "message.car.changed" {
		t.Errorf("event_type = %q", ce.EventType)
	}
	if ce.EntityKind != "car" || ce.EntityID != 42 {
		t.Errorf("entity = %q/%d, want car/42", ce.EntityKind, ce.EntityID)
	}
	if ce.CompanyName != "ООО Ромашка" {
		t.Errorf("company_name = %q", ce.CompanyName)
	}
	if ce.ActorUserID != "33333333-3333-3333-3333-333333333333" {
		t.Errorf("actor_user_id = %q", ce.ActorUserID)
	}
	if len(ce.Changed) != 2 {
		t.Errorf("changed fields = %d, want 2", len(ce.Changed))
	}
}

func TestDeserializeToChangeEvent_DriverAndTrailer(t *testing.T) {
	driver := []byte(`{"event_type":"message.driver.changed","driver_id":5,"changed":{"phone":{"old":"1","new":"2"}}}`)
	ce, _ := DeserializeToChangeEvent(driver)
	if ce.EntityKind != "driver" || ce.EntityID != 5 {
		t.Errorf("driver entity = %q/%d", ce.EntityKind, ce.EntityID)
	}

	trailer := []byte(`{"event_type":"message.trailer.changed","trailer_id":9,"changed":{"number":{"old":"A","new":"B"}}}`)
	ce2, _ := DeserializeToChangeEvent(trailer)
	if ce2.EntityKind != "trailer" || ce2.EntityID != 9 {
		t.Errorf("trailer entity = %q/%d", ce2.EntityKind, ce2.EntityID)
	}
}

func TestDeserializeToChangeEvent_Trip(t *testing.T) {
	body := []byte(`{
		"event_type":"message.trip.changed",
		"trip_id":100,
		"company_name":"Москва-Казань",
		"changed":{"work_status":{"old":"В работе","new":"В пути"},"executor_id":{"old":null,"new":7}}
	}`)
	ce, err := DeserializeToChangeEvent(body)
	if err != nil {
		t.Fatalf("deserialize: %v", err)
	}
	if ce.EntityKind != "trip" || ce.EntityID != 100 {
		t.Errorf("trip entity = %q/%d", ce.EntityKind, ce.EntityID)
	}
	if ce.ChannelName() != "Изменения по рейсу" {
		t.Errorf("channel = %q", ce.ChannelName())
	}
	out, err := ce.RenderMessage()
	if err != nil {
		t.Fatalf("render: %v", err)
	}
	if !strings.Contains(out, "Рейс #100") {
		t.Errorf("expected trip header, got: %q", out)
	}
	if !strings.Contains(out, "Статус") || !strings.Contains(out, "В пути") {
		t.Errorf("expected status line, got: %q", out)
	}
	if !strings.Contains(out, "Исполнитель") {
		t.Errorf("expected executor label, got: %q", out)
	}
	if strings.Contains(out, "<nil>") {
		t.Errorf("null old value must not render as <nil>, got: %q", out)
	}
	if !strings.Contains(out, "Исполнитель: не указано → 7") {
		t.Errorf("expected «не указано» for null executor_id, got: %q", out)
	}
}

func TestChangeEvent_RenderMessage_NullBrandName(t *testing.T) {
	body := []byte(`{
		"event_type":"message.car.changed",
		"car_id":25002,
		"company_name":"ООО Логистик Белогорья",
		"changed":{"brand_name":{"old":null,"new":"Донгфен"}}
	}`)
	ce, err := DeserializeToChangeEvent(body)
	if err != nil {
		t.Fatalf("deserialize: %v", err)
	}
	out, err := ce.RenderMessage()
	if err != nil {
		t.Fatalf("render: %v", err)
	}
	if strings.Contains(out, "<nil>") {
		t.Errorf("must not contain <nil>, got: %q", out)
	}
	if !strings.Contains(out, "Марка: не указано → Донгфен") {
		t.Errorf("expected human-readable empty brand, got: %q", out)
	}
}

func TestDeserializeToChangeEvent_InvalidJSON(t *testing.T) {
	if _, err := DeserializeToChangeEvent([]byte("{not json")); err == nil {
		t.Fatal("expected parse error")
	}
}

func TestChangeEvent_RenderMessage(t *testing.T) {
	ce, _ := DeserializeToChangeEvent(sampleCarChangedBody())
	out, err := ce.RenderMessage()
	if err != nil {
		t.Fatalf("render: %v", err)
	}
	if !strings.Contains(out, "Машина #42") {
		t.Errorf("expected entity header, got: %q", out)
	}
	if !strings.Contains(out, "ООО Ромашка") {
		t.Errorf("expected company name, got: %q", out)
	}
	if !strings.Contains(out, "VIN") || !strings.Contains(out, "OLDVIN") || !strings.Contains(out, "NEWVIN") {
		t.Errorf("expected VIN change line, got: %q", out)
	}
	if !strings.Contains(out, "Тип собственности") {
		t.Errorf("expected ownership label, got: %q", out)
	}
}

func TestChangeEvent_RenderMessage_EmptyChanged(t *testing.T) {
	ce := ChangeEvent{EventType: "message.car.changed", EntityKind: "car", EntityID: 1}
	if _, err := ce.RenderMessage(); err == nil {
		t.Fatal("expected error on empty changed")
	}
}

func TestChangeEvent_ChannelName(t *testing.T) {
	ce, _ := DeserializeToChangeEvent(sampleCarChangedBody())
	// Глобальное имя канала — стабильно, без id сущности/компании.
	if ce.ChannelName() != "Изменения по машине" {
		t.Errorf("unexpected channel name: %q", ce.ChannelName())
	}
}

// --- события с pre-rendered текстом (простои/согласования) ---

func sampleDowntimeRegisteredBody() []byte {
	return []byte(`{
		"event_id": "44444444-4444-4444-4444-444444444444",
		"event_type": "message.downtime.registered",
		"occurred_at": "2026-08-14T10:00:00+00:00",
		"trip_id": 35001,
		"actor_user_id": "55555555-5555-5555-5555-555555555555",
		"text": "Прой зарегистрирован: склад №1, рейс 35001"
	}`)
}

func TestDeserializeToChangeEvent_Downtime(t *testing.T) {
	ce, err := DeserializeToChangeEvent(sampleDowntimeRegisteredBody())
	if err != nil {
		t.Fatalf("deserialize: %v", err)
	}
	if ce.EntityKind != "trip" || ce.EntityID != 35001 {
		t.Errorf("entity = %q/%d, want trip/35001", ce.EntityKind, ce.EntityID)
	}
	if ce.ChannelName() != "Простои" {
		t.Errorf("channel name = %q, want Простои", ce.ChannelName())
	}
	if ce.ChannelEvent() != "message.downtime" {
		t.Errorf("channel event = %q, want message.downtime", ce.ChannelEvent())
	}
	out, err := ce.RenderMessage()
	if err != nil {
		t.Fatalf("render: %v", err)
	}
	if out != "Прой зарегистрирован: склад №1, рейс 35001" {
		t.Errorf("render = %q, want pre-rendered text passthrough", out)
	}
}

func TestDeserializeToChangeEvent_DowntimeResolvedSharesChannel(t *testing.T) {
	body := []byte(`{
		"event_type": "message.downtime.resolved",
		"trip_id": 35001,
		"text": "Простой закрыт"
	}`)
	ce, _ := DeserializeToChangeEvent(body)
	if ce.ChannelEvent() != "message.downtime" {
		t.Errorf("channel event = %q, want message.downtime (shared with registered)", ce.ChannelEvent())
	}
	if ce.ChannelName() != "Простои" {
		t.Errorf("channel name = %q", ce.ChannelName())
	}
}

func TestDeserializeToChangeEvent_ApprovalDistribution(t *testing.T) {
	body := []byte(`{
		"event_type": "message.approval.distribution",
		"text": "Согласование распределения: заявка X"
	}`)
	ce, err := DeserializeToChangeEvent(body)
	if err != nil {
		t.Fatalf("deserialize: %v", err)
	}
	// distribution не имеет числовой сущности — id 0 допустим.
	if ce.EntityKind != "distribution" || ce.EntityID != 0 {
		t.Errorf("entity = %q/%d, want distribution/0", ce.EntityKind, ce.EntityID)
	}
	if ce.ChannelEvent() != "message.approval" || ce.ChannelName() != "Согласования" {
		t.Errorf("channel = %q/%q", ce.ChannelEvent(), ce.ChannelName())
	}
	if out, err := ce.RenderMessage(); err != nil || out != "Согласование распределения: заявка X" {
		t.Errorf("render = %q, %v", out, err)
	}
}

func TestDeserializeToChangeEvent_ApprovalRequested(t *testing.T) {
	body := []byte(`{
		"event_type": "message.approval.requested",
		"trip_id": 77,
		"text": "Запрошено согласование тарифа"
	}`)
	ce, _ := DeserializeToChangeEvent(body)
	if ce.EntityKind != "trip" || ce.EntityID != 77 {
		t.Errorf("entity = %q/%d, want trip/77", ce.EntityKind, ce.EntityID)
	}
	if ce.ChannelEvent() != "message.approval" {
		t.Errorf("channel event = %q", ce.ChannelEvent())
	}
}

func TestChangeEvent_RenderMessage_EmptyPreRenderedText(t *testing.T) {
	ce := ChangeEvent{EventType: "message.downtime.registered", EntityKind: "trip", EntityID: 1}
	if _, err := ce.RenderMessage(); err == nil {
		t.Fatal("expected error on empty pre-rendered text")
	}
}

func TestChangeEvent_ChannelEvent_DefaultIsEventType(t *testing.T) {
	ce, _ := DeserializeToChangeEvent(sampleCarChangedBody())
	if ce.ChannelEvent() != "message.car.changed" {
		t.Errorf("channel event = %q, want event_type fallback", ce.ChannelEvent())
	}
}

func sampleHiringRequestCreatedBody() []byte {
	return []byte(`{
		"event_id": "55555555-5555-5555-5555-555555555555",
		"event_type": "message.hiring_request.created",
		"occurred_at": "2026-08-31T10:00:00+00:00",
		"hiring_request_id": 42,
		"target_role_ids": [2, 3, 4],
		"actor_user_id": "u-1",
		"text": "Создана заявка на подбор З-42\nДолжность: Логист"
	}`)
}

func TestDeserializeToChangeEvent_NewPreRenderedKinds(t *testing.T) {
	cases := []struct {
		eventType    string
		channelEvent string
		channelName  string
		text         string
		tripID       int
	}{
		{"message.downtime.potential", "message.downtime", "Простои", "Потенциальный простой: рейс 11", 11},
		{"message.downtime.act_sent", "message.downtime", "Простои", "Акт простоя отправлен: рейс 12", 12},
		{"message.downtime.act_failed", "message.downtime", "Простои", "Акт простоя не отправлен: рейс 13", 13},
		{"message.tms.sync_blocked", "message.tms", "Синхронизация TMS", "Синхронизация TMS заблокирована: рейс 14", 14},
		{"message.tms.push_failed", "message.tms", "Синхронизация TMS", "Не удалось отправить рейс 14 в TMS", 14},
		{"message.trip.auction_won", "message.trip.auction", "Торги", "Рейс 15: выигрыш торгов", 15},
		{"message.trip.cancelled", "message.trip.cancellation", "Отмены рейсов", "Рейс 15: отмена", 15},
		{"message.trip.breakdown", "message.trip.cancellation", "Отмены рейсов", "Рейс 16: поломка", 16},
		{"message.route_point.unregistered", "message.route_point.alert", "Окна на точках", "Не зарегистрирован на заводе: рейс 17", 17},
		{"message.route_point.belated", "message.route_point.alert", "Окна на точках", "Опоздание на точке: рейс 18", 18},
	}
	for _, tc := range cases {
		t.Run(tc.eventType, func(t *testing.T) {
			body := []byte(fmt.Sprintf(
				`{"event_type":%q,"trip_id":%d,"text":%q}`,
				tc.eventType, tc.tripID, tc.text,
			))
			ce, err := DeserializeToChangeEvent(body)
			if err != nil {
				t.Fatalf("deserialize: %v", err)
			}
			if ce.EntityKind != "trip" || ce.EntityID != tc.tripID {
				t.Errorf("entity = %q/%d, want trip/%d", ce.EntityKind, ce.EntityID, tc.tripID)
			}
			if ce.ChannelEvent() != tc.channelEvent {
				t.Errorf("channel event = %q, want %q", ce.ChannelEvent(), tc.channelEvent)
			}
			if ce.ChannelName() != tc.channelName {
				t.Errorf("channel name = %q, want %q", ce.ChannelName(), tc.channelName)
			}
			out, err := ce.RenderMessage()
			if err != nil {
				t.Fatalf("render: %v", err)
			}
			if out != tc.text {
				t.Errorf("render = %q, want pre-rendered passthrough %q", out, tc.text)
			}
		})
	}
}

func TestChangeEvent_RenderMessage_EmptyTextOnNewPreRenderedKinds(t *testing.T) {
	for _, eventType := range []string{
		"message.downtime.potential",
		"message.tms.sync_blocked",
		"message.tms.push_failed",
		"message.trip.auction_won",
		"message.trip.cancelled",
		"message.route_point.unregistered",
	} {
		ce := ChangeEvent{EventType: eventType, EntityKind: "trip", EntityID: 1}
		if _, err := ce.RenderMessage(); err == nil {
			t.Errorf("%s: expected error on empty pre-rendered text", eventType)
		}
	}
}

func TestDeserializeToChangeEvent_HiringRequestCreated(t *testing.T) {
	ce, err := DeserializeToChangeEvent(sampleHiringRequestCreatedBody())
	if err != nil {
		t.Fatalf("deserialize: %v", err)
	}
	if ce.EntityKind != "hiring_request" || ce.EntityID != 42 {
		t.Errorf("entity = %q/%d, want hiring_request/42", ce.EntityKind, ce.EntityID)
	}
	if len(ce.TargetRoleIDs) != 3 || ce.TargetRoleIDs[0] != 2 {
		t.Errorf("target roles = %v, want [2 3 4]", ce.TargetRoleIDs)
	}
	if ce.ChannelName() != "Заявки на подбор" {
		t.Errorf("channel name = %q, want Заявки на подбор", ce.ChannelName())
	}
	if ce.ChannelEvent() != "message.hiring_request" {
		t.Errorf("channel event = %q, want message.hiring_request", ce.ChannelEvent())
	}
	out, err := ce.RenderMessage()
	if err != nil {
		t.Fatalf("render: %v", err)
	}
	if out != "Создана заявка на подбор З-42\nДолжность: Логист" {
		t.Errorf("render = %q, want pre-rendered text passthrough", out)
	}
}
