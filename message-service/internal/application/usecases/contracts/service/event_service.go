// internal/application/usecases/contracts/service/event_service.go
package service

import "context"

// EventService обрабатывает события, поступающие из брокера (RabbitMQ).
// Это «точка входа» асинхронной обработки: worker читает сообщение из очереди
// и делегирует его обработку этому сервису.
//
// Контракт намеренно оперирует «сырым» телом события ([]byte): десериализация
// и приведение к доменному типу — ответственность реализации, а не воркера,
// что сохраняет пакет worker предметно-независимым.
//
// Возврат ошибки приводит к Nack(requeue) сообщения в брокере; nil — к Ack.
type EventService interface {
	Handle(ctx context.Context, body []byte) error
}
