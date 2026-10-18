// B10: change the wait's duration (1h -> 24h).
package b10_wait_duration

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/cases/bbase"
)

func V2(ctx durable.Context, order string) (string, error) {
	if _, err := durable.Step(ctx, "validate", func(durable.StepContext) (bool, error) { return true, nil }); err != nil {
		return "", err
	}
	res, err := durable.Step(ctx, "reserve", func(durable.StepContext) (bbase.Reservation, error) {
		return bbase.Reservation{ID: "R-42", Price: 100}, nil
	})
	if err != nil {
		return "", err
	}
	if err := durable.Wait(ctx, "pause", 24*time.Hour); err != nil {
		return "", err
	}
	return durable.Step(ctx, "charge", func(durable.StepContext) (string, error) {
		return fmt.Sprintf("charged %s %d", res.ID, res.Price), nil
	})
}

var Case = bbase.Changed("B10", "change the wait duration", V2, nil)
