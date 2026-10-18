// A05: the same map order bug, but the keys are copied into a slice first
// (without sorting), so the range over the map creates no operation itself.
package a05_map_keys_slice

import (
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/lab"
)

var items = map[string]int{"apple": 1, "bread": 2, "cheese": 3}

func Handler(ctx durable.Context, _ string) (int, error) {
	names := make([]string, 0, len(items))
	for name := range items {
		names = append(names, name) // forgot sort.Strings(names)
	}
	total := 0
	for _, name := range names {
		qty := items[name]
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

var Case = lab.Case{ID: "A05", Group: "A", Title: "map keys copied to an unsorted slice, then steps",
	Run: func() lab.Outcome {
		f, fin, err := lab.Resume(Handler, Handler, "order-1", nil)
		return lab.Classify(f, fin, err, func(raw string) (bool, string) { return raw == "6", "total " + raw })
	}, Golden: lab.StableGolden(Handler, "order-1")}
