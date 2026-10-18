// B03: insert a new step before the wait (inside the completed part).
package b03_insert_before

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
	if _, err := durable.Step(ctx, "fraud-check", func(durable.StepContext) (bool, error) { return true, nil }); err != nil {
		return "", err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return "", err
	}
	return durable.Step(ctx, "charge", func(durable.StepContext) (string, error) {
		return fmt.Sprintf("charged %s %d", res.ID, res.Price), nil
	})
}

var Case = bbase.Changed("B03", "insert a step before the wait", V2, nil)
