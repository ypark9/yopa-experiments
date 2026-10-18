// B06: remove a step that has not run yet (charge).
package b06_remove_pending

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
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return "", err
	}
	return fmt.Sprintf("reserved %s %d", res.ID, res.Price), nil
}

var Case = bbase.Changed("B06", "remove a step that has not run", V2, nil)
