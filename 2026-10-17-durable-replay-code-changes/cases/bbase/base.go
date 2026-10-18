// Package bbase holds v1 of the order workflow that every B case changes.
package bbase

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

type Reservation struct {
	ID    string `json:"id"`
	Price int    `json:"price"`
}

// V1 is the deployed code. The first invocation runs validate and reserve,
// then suspends on the wait. Each B case deploys a V2 while it is paused.
func V1(ctx durable.Context, order string) (string, error) {
	if _, err := durable.Step(ctx, "validate", func(durable.StepContext) (bool, error) { return true, nil }); err != nil {
		return "", err
	}
	res, err := durable.Step(ctx, "reserve", func(durable.StepContext) (Reservation, error) {
		return Reservation{ID: "R-42", Price: 100}, nil
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

// Changed builds a B case: resume a V1 execution on v2 and compare the
// result with a fresh v2 execution.
func Changed(id, title string, v2 durable.Handler[string, string], beforeResume func()) lab.Case {
	return lab.Case{ID: id, Group: "B", Title: title, Run: func() lab.Outcome {
		f, fin, err := lab.Resume(V1, v2, "order-1", beforeResume)
		return lab.Classify(f, fin, err, lab.SameAsFresh(v2, "order-1"))
	}, Golden: func() bool {
		return !lab.SigEqual(lab.Signature(V1, "order-1"), lab.Signature(v2, "order-1"))
	}}
}
