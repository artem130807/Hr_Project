package change_events_to_message

import "fmt"

type MessageType string

const (
	TypeCarUpdate              MessageType = "message.car.changed"
	TypeDriverUpdate           MessageType = "message.driver.changed"
	TypeTrailerUpdate          MessageType = "message.trailer.changed"
	TypeHiringRequestCreated   MessageType = "message.hiring_request.created"
	TypeAdaptationTalkHR       MessageType = "message.adaptation.talk_hr"
	TypeAdaptationNotification MessageType = "message.adaptation.notification"
)

var messageTemplates = map[MessageType]string{
	TypeCarUpdate:     "Обновлена машина у исполнителя:",
	TypeDriverUpdate:  "Обновлен водитель у исполнителя",
	TypeTrailerUpdate: "Обновлен прицеп у исполнителя",
}

func GetMessageTemplate(msgType MessageType) string {
	tmpl := messageTemplates[msgType]
	return tmpl
}

func FormatMessage(msgType MessageType, event ChangeEvent) string {
	tmpl := GetMessageTemplate(msgType)
	result := tmpl + fmt.Sprintf("Компания: %s, Изменилось %s, данные: было %s, стало %s", event.CompanyName, event.Changed.NameProperty, event.Changed.Result.Old, event.Changed.Result.New)
	return result
}
