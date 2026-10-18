// B05: remove a completed step (validate).
package b05_remove_done

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/cases/bbase"
)

func V2(ctx durable.Context, order string) (string, error) {
	res, err := durable.Step(ctx, "reserve", func(durable.StepContext) (bbase.Reservation, error) {
		return bbase.Reservation{ID: "R-42", Price: 100}, nil
	})
	if err != nil {
		return "", err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return "", err
	}
	return durable.Step(ctx, "charge", func(durable.StepContext) (string, error) {
		return fmt.Sprintf("charged %s %d", res.ID, res.Price), nil
	})
}

var Case = bbase.Changed("B05", "remove a completed step", V2, nil)
