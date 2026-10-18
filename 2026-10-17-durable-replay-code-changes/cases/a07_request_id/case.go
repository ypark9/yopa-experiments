// A07: ctx.RequestID() used as a key between operations.
package a07_request_id

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

type Out struct{ ReserveKey, ChargeKey string }

func Handler(ctx durable.Context, _ string) (Out, error) {
	key := ctx.RequestID()
	r, err := durable.Step(ctx, "reserve", func(durable.StepContext) (string, error) { return key, nil })
	if err != nil {
		return Out{}, err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return Out{}, err
	}
	c, err := durable.Step(ctx, "charge", func(durable.StepContext) (string, error) { return key, nil })
	return Out{ReserveKey: r, ChargeKey: c}, err
}

var Case = lab.Case{ID: "A07", Group: "A", Title: "ctx.RequestID() used as a key",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) {
			o := mustOut(raw)
			return o.ReserveKey == o.ChargeKey, fmt.Sprintf("reserve key == charge key: %v (reserve %q, charge %q)", o.ReserveKey == o.ChargeKey, o.ReserveKey, o.ChargeKey)
		})
	}, Golden: lab.StableGolden(Handler, "order-1")}
