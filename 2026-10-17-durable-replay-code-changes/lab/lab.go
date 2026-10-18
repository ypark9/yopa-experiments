// Package lab drives durable handlers through the SDK's local runner
// (durabletest). Everything runs in memory: no AWS account, no network.
package lab

import (
	"sync/atomic"

	"github.com/aws/aws-durable-execution-sdk-go/durable"
	"github.com/aws/aws-durable-execution-sdk-go/durable/durabletest"
)

// Outcome is one trial of one case.
type Outcome struct {
	Verdict   string `json:"verdict"`              // ok | silent | nde | error:<type> | first-run-error:<type>
	ErrorType string `json:"error_type,omitempty"` // recorded error type, if any
	Detail    string `json:"detail,omitempty"`
}

// Case is one scenario. Run performs one trial.
type Case struct {
	ID    string
	Group string // "A" same code replayed, "B" code changed while paused
	Title string
	Run   func() Outcome
	// Golden reports whether a golden-signature test (the operation list of
	// a fresh run, compared with a recorded one) would fail on this trial.
	Golden func() bool
}

// SigEqual compares two signatures.
func SigEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// StableGolden returns a Golden func for unchanged code: it records the
// signature of the first fresh run and reports a failure whenever a later
// fresh run produces a different one.
func StableGolden[I, O any](h durable.Handler[I, O], in I) func() bool {
	var ref []string
	return func() bool {
		s := Signature(h, in)
		if ref == nil {
			ref = s
			return false
		}
		return !SigEqual(ref, s)
	}
}

// Resume starts an execution with v1, lets the first invocation run until
// it suspends on a wait, then switches the handler to v2 and drives the
// same execution (same checkpoint log) to the end. With v1 == v2 this is a
// plain suspend-and-replay of unchanged code.
//
// beforeResume, if not nil, runs between the two invocations (used to flip
// an environment variable).
func Resume[I, O any](v1, v2 durable.Handler[I, O], in I, beforeResume func()) (first, final *durabletest.TestResult, err error) {
	var version atomic.Int32
	version.Store(1)
	h := func(ctx durable.Context, e I) (O, error) {
		if version.Load() == 1 {
			return v1(ctx, e)
		}
		return v2(ctx, e)
	}
	r := durabletest.NewLocalRunner(durable.Handler[I, O](h))
	first, err = r.Run(in) // one invocation: runs until the wait suspends it
	if err != nil {
		return nil, nil, err
	}
	if first.Status != durabletest.Pending {
		return first, first, nil
	}
	version.Store(2)
	if beforeResume != nil {
		beforeResume()
	}
	final, err = r.RunUntilComplete(in)
	return first, final, err
}

// Fresh runs an execution of h from start to finish.
func Fresh[I, O any](h durable.Handler[I, O], in I) (*durabletest.TestResult, error) {
	return durabletest.NewLocalRunner(h).RunUntilComplete(in)
}

// Classify turns a Resume result into an Outcome. consistent is called only
// when the execution succeeded; it reports whether the output is what a
// correct run would produce.
func Classify(first, final *durabletest.TestResult, err error, consistent func(raw string) (bool, string)) Outcome {
	if err != nil {
		return Outcome{Verdict: "runner-error", Detail: err.Error()}
	}
	if first.Status == durabletest.Failed {
		return Outcome{Verdict: "first-run-error:" + first.Error.Type, ErrorType: first.Error.Type, Detail: trim(first.Error.Message)}
	}
	switch final.Status {
	case durabletest.Failed:
		if final.Error.Type == "NonDeterministicExecutionError" {
			return Outcome{Verdict: "nde", ErrorType: final.Error.Type, Detail: trim(final.Error.Message)}
		}
		return Outcome{Verdict: "error:" + final.Error.Type, ErrorType: final.Error.Type, Detail: trim(final.Error.Message)}
	case durabletest.Succeeded:
		ok, why := consistent(final.RawResult)
		if ok {
			return Outcome{Verdict: "ok", Detail: why}
		}
		return Outcome{Verdict: "silent", Detail: why}
	default:
		return Outcome{Verdict: "pending", Detail: string(final.Status)}
	}
}

// SameAsFresh reports whether raw equals the result of a fresh run of h.
func SameAsFresh[I, O any](h durable.Handler[I, O], in I) func(string) (bool, string) {
	return func(raw string) (bool, string) {
		f, err := Fresh(h, in)
		if err != nil || f.Status != durabletest.Succeeded {
			return false, "fresh run did not succeed"
		}
		if f.RawResult == raw {
			return true, "matches fresh v2 run: " + raw
		}
		return false, "resumed " + raw + " vs fresh v2 " + f.RawResult
	}
}

// Signature is the operation sequence (type/subtype/name) of a fresh run,
// the same fields durabletest.AssertGoldenSignature compares, minus status.
func Signature[I, O any](h durable.Handler[I, O], in I) []string {
	f, err := Fresh(h, in)
	if err != nil {
		return nil
	}
	var s []string
	for _, op := range durabletest.EventSignature(f) {
		s = append(s, op.Type+"/"+op.SubType+"/"+op.Name+"/"+op.Status)
	}
	return s
}

func trim(s string) string {
	if len(s) > 300 {
		return s[:300] + "..."
	}
	return s
}
