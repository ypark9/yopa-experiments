// B07: change a completed step's return type (struct -> int).
package b07_return_type

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
	price, err := durable.Step(ctx, "reserve", func(durable.StepContext) (int, error) { return 100, nil })
	if err != nil {
		return "", err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return "", err
	}
	return durable.Step(ctx, "charge", func(durable.StepContext) (string, error) {
		return fmt.Sprintf("charged %d", price), nil
	})
}

var Case = bbase.Changed("B07", "change a completed step's return type", V2, nil)
