// internal/application/outboxrelay/worker.go
package outboxrelay

import (
	"context"
	"log/slog"
	"time"

	messaging "github.com/yourusername/message-service/internal/domain/contracts/messaging"
	repositories "github.com/yourusername/message-service/internal/domain/contracts/repositories"
)

// Worker периодически публикует pending outbox-записи в брокер.
type Worker struct {
	uow       repositories.UnitOfWork
	publisher messaging.Publisher
	interval  time.Duration
	batchSize int
	log       *slog.Logger
}

func New(
	uow repositories.UnitOfWork,
	publisher messaging.Publisher,
	interval time.Duration,
	batchSize int,
	log *slog.Logger,
) *Worker {
	if interval <= 0 {
		interval = 2 * time.Second
	}
	if batchSize < 1 {
		batchSize = 50
	}
	if log == nil {
		log = slog.Default()
	}
	return &Worker{
		uow:       uow,
		publisher: publisher,
		interval:  interval,
		batchSize: batchSize,
		log:       log,
	}
}

// Run блокируется до отмены ctx.
func (w *Worker) Run(ctx context.Context) error {
	w.log.Info("outbox relay started", "interval", w.interval, "batch_size", w.batchSize)
	ticker := time.NewTicker(w.interval)
	defer ticker.Stop()

	for {
		if err := w.flush(ctx); err != nil {
			w.log.Error("outbox relay flush failed", "err", err)
		}
		select {
		case <-ctx.Done():
			w.log.Info("outbox relay stopped")
			return nil
		case <-ticker.C:
		}
	}
}

func (w *Worker) flush(ctx context.Context) error {
	var pendingIDs []int64
	var payloads [][]byte

	err := w.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
		rows, err := repos.Outbox().FindPending(ctx, w.batchSize)
		if err != nil {
			return err
		}
		for _, row := range rows {
			pendingIDs = append(pendingIDs, row.ID)
			payloads = append(payloads, append([]byte(nil), row.Payload...))
		}
		return nil
	})
	if err != nil {
		return err
	}
	if len(pendingIDs) == 0 {
		return nil
	}

	for i, id := range pendingIDs {
		if err := w.publisher.Publish(ctx, payloads[i]); err != nil {
			w.log.Warn("outbox publish failed, will retry", "id", id, "err", err)
			return err
		}
		markErr := w.uow.Do(ctx, func(ctx context.Context, repos repositories.Repositories) error {
			return repos.Outbox().MarkPublished(ctx, id)
		})
		if markErr != nil {
			w.log.Error("outbox mark published failed", "id", id, "err", markErr)
			return markErr
		}
		w.log.Info("outbox published", "id", id)
	}
	return nil
}
