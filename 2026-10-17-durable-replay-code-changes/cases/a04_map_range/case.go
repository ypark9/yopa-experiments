// A04: ranging over a map and creating one step per key.
package a04_map_range

import (
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

var items = map[string]int{"apple": 1, "bread": 2, "cheese": 3}

func Handler(ctx durable.Context, _ string) (int, error) {
	total := 0
	for name, qty := range items {
		n, err := durable.Step(ctx, "pack-"+name, func(durable.StepContext) (int, error) { return qty, nil })
		if err != nil {
			return 0, err
		}
		total += n
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return 0, err
	}
	return total, nil
}

var Case = lab.Case{ID: "A04", Group: "A", Title: "range over a map creates steps",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) { return raw == "6", "total " + raw })
	}, Golden: lab.StableGolden(Handler, "order-1")}
