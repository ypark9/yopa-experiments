package a02_rand_key

import "encoding/json"

func mustOut(raw string) Out {
	var o Out
	if err := json.Unmarshal([]byte(raw), &o); err != nil {
		panic(err)
	}
	return o
}
