// internal/application/usecases/change_event.go
//
// Преобразование сырого события из RabbitMQ (message.*.changed) в доменный
// ChangeEvent и построение текста сообщения по шаблону для конкретного типа.
package usecases

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

// EntityChangedEvent — контракт JSON события message.{car,driver,trailer,trip}.changed
// и канальных pre-rendered событий (простои, согласования, заявки на подбор HR),
// публикуемых в очередь message.entity_changed.
// Text — готовый текст уведомления для событий с pre-rendered шаблоном
// (message.downtime.*, message.approval.*, message.tms.*, message.trip.cancelled|breakdown,
// message.route_point.*): erp-backend собирает его сам, имея доступ к ORM-данным,
// message-service использует как есть.
type EntityChangedEvent struct {
	EventID          string                    `json:"event_id"`
	EventType        string                    `json:"event_type"`
	OccurredAt       string                    `json:"occurred_at"`
	ExecutorID       *int64                    `json:"executor_id"`
	CompanyName      string                    `json:"company_name"`
	ActorUserID      string                    `json:"actor_user_id"`
	CarID            *int64                    `json:"car_id"`
	DriverID         *int64                    `json:"driver_id"`
	TrailerID        *int64                    `json:"trailer_id"`
	TripID           *int64                    `json:"trip_id"`
	HiringRequestID  *int64                    `json:"hiring_request_id"`
	CheckpointID     *int64                    `json:"checkpoint_id"`
	TargetRoleIDs    []int                     `json:"target_role_ids"`
	NotificationType string                    `json:"notification_type"`
	TmsID            string                    `json:"tms_id"`
	Changed          map[string]map[string]any `json:"changed"`
	Text             string                    `json:"text"`
}

// parseEntityChanged разбирает «сырое» тело события.
func parseEntityChanged(body []byte) (EntityChangedEvent, error) {
	var ev EntityChangedEvent
	err := json.Unmarshal(body, &ev)
	return ev, err
}

// FieldChange — изменение одного поля: старое и новое значения.
type FieldChange struct {
	Field string
	Old   any
	New   any
}

// ChangeEvent — доменное представление события об изменении сущности.
// Получается из EntityChangedEvent через DeserializeToChangeEvent.
type ChangeEvent struct {
	EventType        string                    // message.car|driver|trailer|trip.changed
	EntityKind       string                    // car / driver / trailer / trip / distribution / hiring_request
	EntityID         int                       // id сущности (0 допустим для distribution)
	CompanyName      string                    // компания исполнителя или маршрут рейса
	ActorUserID      string                    // кто внёс изменение
	Changed          map[string]map[string]any // {field: {"old":..., "new":...}}
	Text             string                    // pre-rendered текст (downtime / approval / hiring_request / tms / trip cancel / route_point)
	EventID          string
	OccurredAt       string
	TargetRoleIDs    []int
	NotificationType string
}

// DeserializeToChangeEvent преобразует тело сообщения из RabbitMQ в ChangeEvent.
// Резолвит kind/id по event_type (car→car_id, driver→driver_id, trailer→trailer_id).
func DeserializeToChangeEvent(body []byte) (ChangeEvent, error) {
	raw, err := parseEntityChanged(body)
	if err != nil {
		return ChangeEvent{}, err
	}

	kind, id := entityRef(raw)
	return ChangeEvent{
		EventType:        raw.EventType,
		EntityKind:       kind,
		EntityID:         id,
		CompanyName:      raw.CompanyName,
		ActorUserID:      raw.ActorUserID,
		Changed:          raw.Changed,
		Text:             raw.Text,
		EventID:          raw.EventID,
		OccurredAt:       raw.OccurredAt,
		TargetRoleIDs:    append([]int(nil), raw.TargetRoleIDs...),
		NotificationType: raw.NotificationType,
	}, nil
}

func entityRef(raw EntityChangedEvent) (kind string, id int) {
	switch raw.EventType {
	case "message.car.changed":
		return "car", intFromPtr(raw.CarID)
	case "message.driver.changed":
		return "driver", intFromPtr(raw.DriverID)
	case "message.trailer.changed":
		return "trailer", intFromPtr(raw.TrailerID)
	case "message.trip.changed":
		return "trip", intFromPtr(raw.TripID)
	case "message.downtime.registered", "message.downtime.resolved",
		"message.downtime.potential", "message.downtime.act_sent", "message.downtime.act_failed",
		"message.tms.sync_blocked", "message.tms.push_failed",
		"message.trip.auction_won",
		"message.trip.cancelled", "message.trip.breakdown",
		"message.route_point.unregistered", "message.route_point.belated":
		return "trip", intFromPtr(raw.TripID)
	case "message.approval.requested":
		return "trip", intFromPtr(raw.TripID)
	case "message.approval.distribution":
		// Согласование распределения не имеет числовой сущности (uid — строка).
		return "distribution", 0
	case "message.hiring_request.created":
		return "hiring_request", intFromPtr(raw.HiringRequestID)
	case "message.adaptation.talk_hr", "message.adaptation.notification":
		return "adaptation_checkpoint", intFromPtr(raw.CheckpointID)
	default:
		return "", 0
	}
}

func intFromPtr(v *int64) int {
	if v == nil {
		return 0
	}
	return int(*v)
}

// messageTypes — реестр «сообщений на конкретный тип события»: каждому event_type
// сопоставляется заголовок и название канала. Это и есть message_type: шаблон
// текста для конкретного типа события.
//
// ChannelEvent — ключ идентификации глобального канала: по умолчанию совпадает
// с event_type; для связанных типов (downtime.registered/resolved,
// approval.requested/distribution) переопределяется, чтобы несколько event_type'ов
// писали в ОДИН канал.
//
// PreRendered — события, текст которых erp-backend собирает сам (поле text);
// message-service не строит шаблон, а использует готовый текст.
var messageTypes = map[string]struct {
	Label        string // «Машина», «Водитель», «Прицеп», «Рейс»
	ChannelName  string // название канала по умолчанию
	ChannelEvent string // ключ канала (пусто == event_type)
	PreRendered  bool   // текст приходит готовым в поле text
}{
	"message.car.changed":              {Label: "Машина", ChannelName: "Изменения по машине"},
	"message.driver.changed":           {Label: "Водитель", ChannelName: "Изменения по водителю"},
	"message.trailer.changed":          {Label: "Прицеп", ChannelName: "Изменения по прицепу"},
	"message.trip.changed":             {Label: "Рейс", ChannelName: "Изменения по рейсу"},
	"message.downtime.registered":      {Label: "Простой", ChannelName: "Простои", ChannelEvent: "message.downtime", PreRendered: true},
	"message.downtime.resolved":        {Label: "Простой закрыт", ChannelName: "Простои", ChannelEvent: "message.downtime", PreRendered: true},
	"message.downtime.potential":       {Label: "Потенциальный простой", ChannelName: "Простои", ChannelEvent: "message.downtime", PreRendered: true},
	"message.downtime.act_sent":        {Label: "Акт простоя отправлен", ChannelName: "Простои", ChannelEvent: "message.downtime", PreRendered: true},
	"message.downtime.act_failed":      {Label: "Акт простоя не отправлен", ChannelName: "Простои", ChannelEvent: "message.downtime", PreRendered: true},
	"message.tms.sync_blocked":         {Label: "Синхронизация TMS", ChannelName: "Синхронизация TMS", ChannelEvent: "message.tms", PreRendered: true},
	"message.tms.push_failed":          {Label: "Ошибка синхронизации TMS", ChannelName: "Синхронизация TMS", ChannelEvent: "message.tms", PreRendered: true},
	"message.trip.auction_won":         {Label: "Выигрыш торгов", ChannelName: "Торги", ChannelEvent: "message.trip.auction", PreRendered: true},
	"message.trip.cancelled":           {Label: "Отмена рейса", ChannelName: "Отмены рейсов", ChannelEvent: "message.trip.cancellation", PreRendered: true},
	"message.trip.breakdown":           {Label: "Поломка рейса", ChannelName: "Отмены рейсов", ChannelEvent: "message.trip.cancellation", PreRendered: true},
	"message.route_point.unregistered": {Label: "Нет регистрации на заводе", ChannelName: "Окна на точках", ChannelEvent: "message.route_point.alert", PreRendered: true},
	"message.route_point.belated":      {Label: "Опоздание на точке", ChannelName: "Окна на точках", ChannelEvent: "message.route_point.alert", PreRendered: true},
	"message.approval.requested":       {Label: "Согласование", ChannelName: "Согласования", ChannelEvent: "message.approval", PreRendered: true},
	"message.approval.distribution":    {Label: "Согласование распределения", ChannelName: "Согласования", ChannelEvent: "message.approval", PreRendered: true},
	"message.hiring_request.created":   {Label: "Заявка на подбор", ChannelName: "Заявки на подбор", ChannelEvent: "message.hiring_request", PreRendered: true},
	"message.adaptation.talk_hr":       {Label: "Запрос разговора с HR", PreRendered: true},
	"message.adaptation.notification":  {Label: "Адаптация", PreRendered: true},
}

// fieldLabels — человекочитаемые названия полей для текста уведомления.
var fieldLabels = map[string]string{
	"number":                      "Гос. номер",
	"vin":                         "VIN",
	"owner_phone":                 "Владелец",
	"glonass":                     "Глонасс",
	"brand_name":                  "Марка",
	"tech_passport":               "СТС",
	"imei":                        "IMEI",
	"ownership_type_name":         "Тип собственности",
	"carrier_ownership_type_name": "Собственность перевозчика",
	"final_carrier_name":          "Конечный перевозчик",
	"final_carrier_inn":           "ИНН перевозчика",
	"first_name":                  "Фамилия",
	"last_name":                   "Имя",
	"surname":                     "Отчество",
	"birthday":                    "Дата рождения",
	"inn":                         "ИНН",
	"passport":                    "Паспорт",
	"license":                     "Вод. удостоверение",
	"phone":                       "Телефон",
	"passport_issued":             "Паспорт выдан",
	"work_status":                 "Статус",
	"executor_id":                 "Исполнитель",
	"customer_id":                 "Заказчик",
	"responsible_id":              "Ответственный",
	"executor_price":              "Ставка исполнителя",
	"nds":                         "НДС",
	"payment_methods_id":          "Форма оплаты",
	"payment_terms_id":            "Сроки оплаты",
	"approval":                    "Согласование",
}

// eventTypeChannelEntityID — фиктивный EntityID для глобальных каналов «один на тип
// события». Домен (domain.NewChannel) требует EntityID > 0; канал на event_type
// идентифицируется парой (event_type, это значение). Все события данного типа
// (любой car_id/driver_id/trailer_id) постятся в один и тот же канал.
const eventTypeChannelEntityID = 1

// ChannelName возвращает стабильное название глобального канала для типа события
// (не зависит от конкретной сущности — поэтому канал один на тип).
func (ce ChangeEvent) ChannelName() string {
	if mt, ok := messageTypes[ce.EventType]; ok {
		return mt.ChannelName
	}
	return "Изменения по сущности"
}

// ChannelEvent возвращает ключ глобального канала: для связанных event_type'ов
// (downtime.*, approval.*) — общий, чтобы все они писали в один канал.
func (ce ChangeEvent) ChannelEvent() string {
	if mt, ok := messageTypes[ce.EventType]; ok && mt.ChannelEvent != "" {
		return mt.ChannelEvent
	}
	return ce.EventType
}

// preRendered сообщает, приходит ли текст события готовым (поле text от erp-backend).
func (ce ChangeEvent) preRendered() bool {
	mt, ok := messageTypes[ce.EventType]
	return ok && mt.PreRendered
}

// RenderMessage строит текст уведомления по шаблону для типа события.
func (ce ChangeEvent) RenderMessage() (string, error) {
	// События с pre-rendered текстом (простои/согласования): erp-backend уже
	// собрал полный текст из ORM-данных, передаём как есть.
	if ce.preRendered() {
		if ce.Text == "" {
			return "", fmt.Errorf("change_event: empty pre-rendered text")
		}
		return ce.Text, nil
	}

	if len(ce.Changed) == 0 {
		return "", fmt.Errorf("change_event: empty changed")
	}

	mt, ok := messageTypes[ce.EventType]
	label := mt.Label
	if !ok {
		label = ce.EntityKind
	}

	var b strings.Builder
	fmt.Fprintf(&b, "%s #%d", label, ce.EntityID)
	if ce.CompanyName != "" {
		fmt.Fprintf(&b, " (%s)", ce.CompanyName)
	}
	b.WriteString(" — обновлены данные:\n")

	// Детерминированный порядок полей — сортируем по имени поля.
	for _, field := range sortedKeys(ce.Changed) {
		ch := ce.Changed[field]
		fmt.Fprintf(&b, "• %s: %s → %s\n", fieldLabel(field), formatChangeValue(ch["old"]), formatChangeValue(ch["new"]))
	}
	return b.String(), nil
}

// formatChangeValue печатает значение diff для человека.
// JSON null (Go nil) и пустая строка → «не указано», а не служебное <nil>.
func formatChangeValue(v any) string {
	if v == nil {
		return "не указано"
	}
	s := strings.TrimSpace(fmt.Sprint(v))
	if s == "" || s == "<nil>" {
		return "не указано"
	}
	return s
}

func fieldLabel(field string) string {
	if l, ok := fieldLabels[field]; ok {
		return l
	}
	return field
}

func sortedKeys(m map[string]map[string]any) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}
