// A01: time.Now() read between operations and used as an idempotency key.
package a01_time_now

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

type Out struct{ ReserveKey, ChargeKey int64 }

func Handler(ctx durable.Context, _ string) (Out, error) {
	key := time.Now().UnixNano() // outside any step
	r, err := durable.Step(ctx, "reserve", func(durable.StepContext) (int64, error) { return key, nil })
	if err != nil {
		return Out{}, err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return Out{}, err
	}
	c, err := durable.Step(ctx, "charge", func(durable.StepContext) (int64, error) { return key, nil })
	return Out{ReserveKey: r, ChargeKey: c}, err
}

var Case = lab.Case{ID: "A01", Group: "A", Title: "time.Now() outside a step, used as idempotency key",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) {
			o := mustOut(raw)
			return o.ReserveKey == o.ChargeKey, fmt.Sprintf("reserve key == charge key: %v", o.ReserveKey == o.ChargeKey)
		})
	}, Golden: lab.StableGolden(Handler, "order-1")}
