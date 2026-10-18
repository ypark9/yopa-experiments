// B14: no code change. An environment variable read between operations
// flips while the execution is paused (a configuration update).
package b14_env_flag

import (
	"fmt"
	"os"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/cases/bbase"
	"replaylab/lab"
)

func Handler(ctx durable.Context, order string) (string, error) {
	if _, err := durable.Step(ctx, "validate", func(durable.StepContext) (bool, error) { return true, nil }); err != nil {
		return "", err
	}
	if os.Getenv("FRAUD_CHECK") == "on" {
		if _, err := durable.Step(ctx, "fraud-check", func(durable.StepContext) (bool, error) { return true, nil }); err != nil {
			return "", err
		}
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
	return durable.Step(ctx, "charge", func(durable.StepContext) (string, error) {
		return fmt.Sprintf("charged %s %d", res.ID, res.Price), nil
	})
}

var Case = lab.Case{ID: "B14", Group: "B", Title: "env var read between operations flips while paused",
	Run: func() lab.Outcome {
		os.Setenv("FRAUD_CHECK", "off")
		defer os.Unsetenv("FRAUD_CHECK")
		f, fin, err := lab.Resume(Handler, Handler, "order-1", func() { os.Setenv("FRAUD_CHECK", "on") })
		return lab.Classify(f, fin, err, func(raw string) (bool, string) { return true, raw })
	}, Golden: lab.StableGolden(Handler, "order-1")}
