// B13: add a field to a completed step's result and use it later.
package b13_add_field

import (
	"fmt"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"

	"replaylab/cases/bbase"
)

type Reservation struct {
	ID       string `json:"id"`
	Price    int    `json:"price"`
	Currency string `json:"currency"` // new
}

func V2(ctx durable.Context, order string) (string, error) {
	if _, err := durable.Step(ctx, "validate", func(durable.StepContext) (bool, error) { return true, nil }); err != nil {
		return "", err
	}
	res, err := durable.Step(ctx, "reserve", func(durable.StepContext) (Reservation, error) {
		return Reservation{ID: "R-42", Price: 100, Currency: "USD"}, nil
	})
	if err != nil {
		return "", err
	}
	if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
		return "", err
	}
	return durable.Step(ctx, "charge", func(durable.StepContext) (string, error) {
		return fmt.Sprintf("charged %s %d %s", res.ID, res.Price, res.Currency), nil
	})
}

var Case = bbase.Changed("B13", "add a field to a completed step's result", V2, nil)
