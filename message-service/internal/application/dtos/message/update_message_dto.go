package message

// UpdateMessageDto — входной DTO для редактирования содержимого сообщения.
// Согласно доменной логике контент можно изменить только до отправки.
type UpdateMessageDto struct {
	Content string `json:"content" binding:"required"`
}
