// A02: math/rand key generated between operations.
package a02_rand_key

import (
	"fmt"
	"math/rand/v2"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

type Out struct{ ReserveKey, ChargeKey uint64 }

func Handler(ctx durable.Context, _ string) (Out, error) {
	key := rand.Uint64() // outside any step
	r, err := durable.Step(ctx, "reserve", func(durable.StepContext) (uint64, error) { return key, nil })
	if err != nil {
		return Out{}, err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return Out{}, err
	}
	c, err := durable.Step(ctx, "charge", func(durable.StepContext) (uint64, error) { return key, nil })
	return Out{ReserveKey: r, ChargeKey: c}, err
}

var Case = lab.Case{ID: "A02", Group: "A", Title: "rand key outside a step",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) {
			o := mustOut(raw)
			return o.ReserveKey == o.ChargeKey, fmt.Sprintf("reserve key == charge key: %v", o.ReserveKey == o.ChargeKey)
		})
	}, Golden: lab.StableGolden(Handler, "order-1")}
