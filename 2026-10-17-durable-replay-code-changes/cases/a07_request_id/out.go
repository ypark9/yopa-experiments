package a07_request_id

import "encoding/json"

func mustOut(raw string) Out {
	var o Out
	if err := json.Unmarshal([]byte(raw), &o); err != nil {
		panic(err)
	}
	return o
}
