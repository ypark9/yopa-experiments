// A09: control. The key is made inside a step; the timestamp comes from
// durable.ExecutionStartTime; map keys are sorted.
package a09_control_safe

import (
	"fmt"
	"math/rand/v2"
	"sort"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

type Out struct {
	ReserveKey, ChargeKey uint64
	StartA, StartB        int64
	Total                 int
}

var items = map[string]int{"apple": 1, "bread": 2, "cheese": 3}

func Handler(ctx durable.Context, _ string) (Out, error) {
	start := durable.ExecutionStartTime(ctx).UnixNano()
	startA, err := durable.Step(ctx, "stamp", func(durable.StepContext) (int64, error) { return start, nil })
	if err != nil {
		return Out{}, err
	}
	key, err := durable.Step(ctx, "make-key", func(durable.StepContext) (uint64, error) { return rand.Uint64(), nil })
	if err != nil {
		return Out{}, err
	}
	names := make([]string, 0, len(items))
	for n := range items {
		names = append(names, n)
	}
	sort.Strings(names)
	total := 0
	for _, n := range names {
		qty := items[n]
		v, err := durable.Step(ctx, "pack-"+n, func(durable.StepContext) (int, error) { return qty, nil })
		if err != nil {
			return Out{}, err
		}
		total += v
	}
	r, err := durable.Step(ctx, "reserve", func(durable.StepContext) (uint64, error) { return key, nil })
	if err != nil {
		return Out{}, err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return Out{}, err
	}
	c, err := durable.Step(ctx, "charge", func(durable.StepContext) (uint64, error) { return key, nil })
	startB := durable.ExecutionStartTime(ctx).UnixNano()
	return Out{ReserveKey: r, ChargeKey: c, StartA: startA, StartB: startB, Total: total}, err
}

var Case = lab.Case{ID: "A09", Group: "A", Title: "control: key in a step, ExecutionStartTime, sorted keys",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) {
			o := mustOut(raw)
			ok := o.ReserveKey == o.ChargeKey && o.Total == 6 && o.StartA == o.StartB
			return ok, fmt.Sprintf("keys equal %v, total %d, ExecutionStartTime same in both invocations %v", o.ReserveKey == o.ChargeKey, o.Total, o.StartA == o.StartB)
		})
	}, Golden: lab.StableGolden(Handler, "order-1")}
