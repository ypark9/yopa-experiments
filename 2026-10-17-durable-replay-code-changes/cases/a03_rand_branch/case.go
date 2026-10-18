// A03: a random branch decides whether an extra step runs before the wait.
package a03_rand_branch

import (
	"math/rand/v2"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

func Handler(ctx durable.Context, _ string) (string, error) {
	if rand.IntN(2) == 0 { // outside any step: a 50% "sampled audit"
		if _, err := durable.Step(ctx, "audit", func(durable.StepContext) (string, error) { return "audited", nil }); err != nil {
			return "", err
		}
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return "", err
	}
	return durable.Step(ctx, "charge", func(durable.StepContext) (string, error) { return "charged", nil })
}

var Case = lab.Case{ID: "A03", Group: "A", Title: "random branch adds a step before the wait",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) { return true, raw })
	}, Golden: lab.StableGolden(Handler, "order-1")}
