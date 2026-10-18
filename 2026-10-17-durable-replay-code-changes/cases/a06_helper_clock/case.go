// A06: the key comes from a helper that has no durable.Context parameter.
package a06_helper_clock

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

type Out struct{ ReserveKey, ChargeKey string }

func newKey() string { return fmt.Sprintf("k-%d", time.Now().UnixNano()) }

func Handler(ctx durable.Context, _ string) (Out, error) {
	key := newKey() // helper reads the clock
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

var Case = lab.Case{ID: "A06", Group: "A", Title: "clock read inside a helper without a Context",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) {
			o := mustOut(raw)
			return o.ReserveKey == o.ChargeKey, fmt.Sprintf("reserve key == charge key: %v", o.ReserveKey == o.ChargeKey)
		})
	}, Golden: lab.StableGolden(Handler, "order-1")}
