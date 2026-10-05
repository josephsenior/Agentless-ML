// Convert go test -json's stream to compact CTRF without retaining events.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: go-json-to-ctrf INPUT OUTPUT")
		os.Exit(2)
	}
	input, err := os.Open(os.Args[1])
	if err != nil {
		fail(err)
	}
	defer input.Close()

	output, err := os.Create(os.Args[2])
	if err != nil {
		fail(err)
	}
	defer output.Close()

	w := bufio.NewWriter(output)
	if _, err := io.WriteString(w, `{"results":{"tests":[`); err != nil {
		fail(err)
	}
	decoder := json.NewDecoder(bufio.NewReader(input))
	encoder := json.NewEncoder(w)
	first := true
	for {
		var event struct {
			Action  string
			Package string
			Test    string
		}
		err := decoder.Decode(&event)
		if err == io.EOF {
			break
		}
		if err != nil {
			fail(err)
		}

		status := ""
		switch event.Action {
		case "pass":
			status = "passed"
		case "fail":
			status = "failed"
		case "skip":
			status = "skipped"
		}
		// Build, package, run and output events have no individual test result.
		if status == "" || event.Test == "" {
			continue
		}
		if !first {
			if err := w.WriteByte(','); err != nil {
				fail(err)
			}
		}
		if err := encoder.Encode(map[string]string{
			"suite": event.Package, "name": event.Test, "status": status,
		}); err != nil {
			fail(err)
		}
		first = false
	}
	if _, err := io.WriteString(w, `]}}`); err != nil {
		fail(err)
	}
	if err := w.Flush(); err != nil {
		fail(err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
