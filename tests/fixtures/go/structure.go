package sample

import "fmt"

type Counter[T ~int] struct {
    Value T
}

type Reader interface {
    Read(p []byte) (int, error)
}

type Alias = int

var (
    First, Second = 1, 2
    Message = "braces: { } and unicode: café"
)

const (
    Zero = iota
    One
)

func (c *Counter[T]) Add(v T) T {
    // A brace in a comment must not end this function: }
    c.Value += v
    return c.Value
}

func Format(v int) string {
    format := func() string { return "{%d}" }
    return fmt.Sprintf(format(), v)
}
