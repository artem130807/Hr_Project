// internal/application/worker/worker.go
package worker

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"sync"

	messaging "github.com/yourusername/message-service/internal/domain/contracts/messaging"
	"github.com/yourusername/message-service/internal/pkg/config"
)

// Handler обрабатывает тело сообщения из брокера.
// Возвращённая ошибка приводит к Nack(requeue=true); nil — к Ack.
type Handler func(ctx context.Context, body []byte) error

// Worker читает сообщения из messaging.Consumer и распределяет их
// пулу горутин-обработчиков через Go-канал.
//
// Поток данных:
//  1. fetch-горутина (fetchLoop): Consumer.Consume → jobs chan;
//  2. N worker-горутин: jobs → Handler;
//  3. fetchLoop получает результат и вызывает Ack/Nack (сериализация
//     ack на одном consumer — гарантируется последовательным pending).
//
// Такая схема даёт параллельную обработку (N воркеров) при сохранении
// строгого порядка подтверждений на стороне брокера.
type Worker struct {
	consumer messaging.Consumer
	handler  Handler
	cfg      config.WorkerConfig
	log      *slog.Logger
}

type job struct {
	body []byte
	done chan error
}

// New создаёт Worker. Нормализует конфиг (минимум 1 воркер/буфер),
// подставляет slog.Default() при отсутствии логгера.
func New(consumer messaging.Consumer, handler Handler, cfg config.WorkerConfig, log *slog.Logger) *Worker {
	if cfg.Concurrency < 1 {
		cfg.Concurrency = 1
	}
	if cfg.Buffer < 1 {
		cfg.Buffer = cfg.Concurrency
	}
	if log == nil {
		log = slog.Default()
	}
	return &Worker{
		consumer: consumer,
		handler:  handler,
		cfg:      cfg,
		log:      log,
	}
}

// Run блокируется до отмены ctx или фатальной ошибки consumer (например,
// закрытие соединения). Возвращает nil для «мягких» завершений
// (context cancelled, consumer closed) и ошибку — в остальных случаях.
func (w *Worker) Run(ctx context.Context) error {
	jobs := make(chan job, w.cfg.Buffer)

	var wg sync.WaitGroup
	for i := 0; i < w.cfg.Concurrency; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			w.runWorker(ctx, workerID, jobs)
		}(i)
	}

	err := w.fetchLoop(ctx, jobs)
	close(jobs)
	wg.Wait()

	if err == nil {
		return nil
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return nil
	}
	if errors.Is(err, messaging.ErrConsumerClosed) {
		return nil
	}
	return err
}

// runWorker —生命周期 одной горутины-обработчика: читает jobs, вызывает handler,
// ловит панику и отдаёт результат обратно в fetchLoop через j.done.
func (w *Worker) runWorker(ctx context.Context, workerID int, jobs <-chan job) {
	for j := range jobs {
		var err error
		func() {
			defer func() {
				if r := recover(); r != nil {
					w.log.Error("worker panic",
						"worker_id", workerID,
						"panic", fmt.Sprintf("%v", r),
					)
					err = fmt.Errorf("handler panic: %v", r)
				}
			}()
			err = w.handler(ctx, j.body)
		}()
		j.done <- err
	}
}

// fetchLoop последовательно: читает сообщение, отдаёт воркеру, ждёт результат,
// делает Ack/Nack. Последовательность ack гарантирует консистентность с брокером.
func (w *Worker) fetchLoop(ctx context.Context, jobs chan<- job) error {
	for {
		body, err := w.consumer.Consume(ctx)
		if err != nil {
			return err
		}

		done := make(chan error, 1)
		item := job{body: body, done: done}

		select {
		case <-ctx.Done():
			// Не успели отдать в обработку — возвращаем в очередь.
			_ = w.consumer.Nack(true)
			return ctx.Err()
		case jobs <- item:
		}

		select {
		case <-ctx.Done():
			_ = w.consumer.Nack(true)
			return ctx.Err()
		case handleErr := <-done:
			if handleErr != nil {
				w.log.Error("message handling failed", "err", handleErr)
				if nackErr := w.consumer.Nack(true); nackErr != nil {
					w.log.Error("nack failed", "err", nackErr)
					return nackErr
				}
				continue
			}
			if ackErr := w.consumer.Ack(); ackErr != nil {
				w.log.Error("ack failed", "err", ackErr)
				return ackErr
			}
		}
	}
}
