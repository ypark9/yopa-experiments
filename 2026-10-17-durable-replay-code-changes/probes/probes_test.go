// Supplementary probes that explain three results in the matrix.
// Run: go test ./probes -v
package probes

import (
	"testing"
	"time"

	"github.com/aws/aws-durable-execution-sdk-go/durable"
	"github.com/aws/aws-durable-execution-sdk-go/durable/durabletest"

	"replaylab/cases/a03_rand_branch"
	"replaylab/cases/b10_wait_duration"
	"replaylab/cases/bbase"
	"replaylab/lab"
)

// How many invocations does one execution of the A03 handler take? Each
// invocation after the first is one more chance for the random branch to
// disagree with the checkpoint.
func TestInvocationsPerExecution(t *testing.T) {
	ok := 0
	for i := 0; i < 50; i++ {
		r, err := lab.Fresh(a03_rand_branch.Handler, "order-1")
		if err != nil {
			t.Fatal(err)
		}
		if r.Status == durabletest.Succeeded {
			ok++
			if ok == 1 {
				t.Logf("A03 succeeded execution: %d invocations", len(r.Invocations))
			}
		}
	}
	r, _ := lab.Fresh(bbase.V1, "order-1")
	t.Logf("B v1 workflow fresh execution: %d invocations", len(r.Invocations))
}

// B10: which duration does the paused wait keep after v2 changes it?
func TestWaitDurationAfterChange(t *testing.T) {
	_, fin, err := lab.Resume(bbase.V1, b10_wait_duration.V2, "order-1", nil)
	if err != nil {
		t.Fatal(err)
	}
	for _, ev := range fin.Events {
		if ev.WaitStartedDetails != nil && ev.WaitStartedDetails.Duration != nil {
			t.Logf("resumed on v2: WaitStarted recorded duration %ds", *ev.WaitStartedDetails.Duration)
		}
	}
	fr, _ := lab.Fresh(b10_wait_duration.V2, "order-1")
	for _, ev := range fr.Events {
		if ev.WaitStartedDetails != nil && ev.WaitStartedDetails.Duration != nil {
			t.Logf("fresh v2: WaitStarted recorded duration %ds", *ev.WaitStartedDetails.Duration)
		}
	}
}

// A07: what does ctx.RequestID() return under the local runner?
func TestRequestIDLocal(t *testing.T) {
	var seen []string
	h := func(ctx durable.Context, _ string) (string, error) {
		seen = append(seen, ctx.RequestID())
		if err := durable.Wait(ctx, "pause", time.Hour); err != nil {
			return "", err
		}
		return "done", nil
	}
	r, err := lab.Fresh(durable.Handler[string, string](h), "x")
	if err != nil {
		t.Fatal(err)
	}
	t.Logf("ctx.RequestID() per invocation: %q", seen)
	for _, inv := range r.Invocations {
		t.Logf("runner-recorded invocation RequestID: %s", inv.RequestID)
	}
}

// How many invocations does the Resume path (Run, then RunUntilComplete)
// take? Every invocation re-runs the handler from the top.
func TestInvocationsResumePath(t *testing.T) {
	_, fin, err := lab.Resume(bbase.V1, bbase.V1, "order-1", nil)
	if err != nil {
		t.Fatal(err)
	}
	t.Logf("Resume path (unchanged v1): %d invocations, status %s", len(fin.Invocations), fin.Status)
}

// How long does one resume-on-new-code check take? (B01 handler pair)
func TestResumeCheckDuration(t *testing.T) {
	const n = 200
	start := time.Now()
	for i := 0; i < n; i++ {
		if _, _, err := lab.Resume(bbase.V1, bbase.V1, "order-1", nil); err != nil {
			t.Fatal(err)
		}
	}
	t.Logf("resume check (v1 -> v1, 3 invocations): %d runs, mean %v per run", n, time.Since(start)/n)
}
