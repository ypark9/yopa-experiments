// A08: a plain goroutine runs a step on the parent context.
package a08_goroutine

import (
	"sync"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

func Handler(ctx durable.Context, _ string) (string, error) {
	var wg sync.WaitGroup
	var a, b string
	var errA, errB error
	wg.Add(2)
	go func() {
		defer wg.Done()
		a, errA = durable.Step(ctx, "email", func(durable.StepContext) (string, error) { return "e", nil })
	}()
	go func() {
		defer wg.Done()
		b, errB = durable.Step(ctx, "sms", func(durable.StepContext) (string, error) { return "s", nil })
	}()
	wg.Wait()
	if errA != nil {
		return "", errA
	}
	if errB != nil {
		return "", errB
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return "", err
	}
	return a + b, nil
}

var Case = lab.Case{ID: "A08", Group: "A", Title: "plain goroutines call Step on the parent context",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) { return raw == `"es"`, raw })
	}, Golden: lab.StableGolden(Handler, "order-1")}
