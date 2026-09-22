package service

import (
	"context"

	dto "github.com/yourusername/message-service/internal/application/dtos/channel"
)

// ChannelService — контракт приложения для работы с каналами.
type ChannelService interface {
	AddChannel(ctx context.Context, request *dto.CreateChannelDto) (*dto.ChannelDto, error)
	RemoveChannel(ctx context.Context, channelID int) error
	EditChannel(ctx context.Context, channelID int, request *dto.UpdateChannelDto) (*dto.ChannelDto, error)
	GetChannel(ctx context.Context, channelID int) (*dto.ChannelDto, error)
	GetChannelsByPush(ctx context.Context, isPush *bool) ([]*dto.ChannelDto, error)
}
