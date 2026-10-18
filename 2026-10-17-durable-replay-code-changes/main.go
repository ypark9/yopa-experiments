// Command replaylab runs every case for -trials trials and prints one JSON
// line per trial, then a per-case tally on stderr.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"runtime"
	"sort"

	"replaylab/cases/a01_time_now"
	"replaylab/cases/a02_rand_key"
	"replaylab/cases/a03_rand_branch"
	"replaylab/cases/a04_map_range"
	"replaylab/cases/a05_map_keys_slice"
	"replaylab/cases/a06_helper_clock"
	"replaylab/cases/a07_request_id"
	"replaylab/cases/a08_goroutine"
	"replaylab/cases/a09_control_safe"
	"replaylab/cases/b01_rename_step"
	"replaylab/cases/b02_reorder_steps"
	"replaylab/cases/b03_insert_before"
	"replaylab/cases/b04_insert_after"
	"replaylab/cases/b05_remove_done"
	"replaylab/cases/b06_remove_pending"
	"replaylab/cases/b07_return_type"
	"replaylab/cases/b08_json_tag"
	"replaylab/cases/b09_body_fix"
	"replaylab/cases/b10_wait_duration"
	"replaylab/cases/b11_rename_wait"
	"replaylab/cases/b12_wrap_child"
	"replaylab/cases/b13_add_field"
	"replaylab/cases/b14_env_flag"
	"replaylab/lab"
)

var all = []lab.Case{
	a01_time_now.Case, a02_rand_key.Case, a03_rand_branch.Case, a04_map_range.Case,
	a05_map_keys_slice.Case, a06_helper_clock.Case, a07_request_id.Case, a08_goroutine.Case,
	a09_control_safe.Case,
	b01_rename_step.Case, b02_reorder_steps.Case, b03_insert_before.Case, b04_insert_after.Case,
	b05_remove_done.Case, b06_remove_pending.Case, b07_return_type.Case, b08_json_tag.Case,
	b09_body_fix.Case, b10_wait_duration.Case, b11_rename_wait.Case, b12_wrap_child.Case,
	b13_add_field.Case, b14_env_flag.Case,
}

type line struct {
	Run    int    `json:"run"`
	Case   string `json:"case"`
	Group  string `json:"group"`
	Title  string `json:"title"`
	Trial  int    `json:"trial"`
	Golden bool   `json:"golden_would_fail"`
	lab.Outcome
}

func main() {
	trials := flag.Int("trials", 20, "trials per case")
	run := flag.Int("run", 1, "run number, recorded in the output")
	flag.Parse()
	fmt.Fprintf(os.Stderr, "go %s %s/%s\n", runtime.Version(), runtime.GOOS, runtime.GOARCH)
	enc := json.NewEncoder(os.Stdout)
	for _, c := range all {
		tally := map[string]int{}
		golden := 0
		for t := 1; t <= *trials; t++ {
			o := c.Run()
			g := c.Golden()
			if g {
				golden++
			}
			tally[o.Verdict]++
			if err := enc.Encode(line{Run: *run, Case: c.ID, Group: c.Group, Title: c.Title, Trial: t, Golden: g, Outcome: o}); err != nil {
				panic(err)
			}
		}
		keys := make([]string, 0, len(tally))
		for k := range tally {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		fmt.Fprintf(os.Stderr, "%s %-55s", c.ID, c.Title)
		for _, k := range keys {
			fmt.Fprintf(os.Stderr, " %s=%d", k, tally[k])
		}
		fmt.Fprintf(os.Stderr, " golden_fail=%d\n", golden)
	}
}
