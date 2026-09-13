package edge

import (
	"fmt"
)

// Grouped var declarations wrap specs in a var_spec_list; single ones do not.
var (
	_      = fmt.Sprintf
	a, b   = 1, 2
	c      int
)

var single, _ = 3, 4

// Grouped const declarations hold const_spec children directly.
const (
	Zero = iota
	One
	_
	Three
)

const Solo = "x"

type (
	Point struct {
		X, Y int
	}
	Shape interface {
		fmt.Stringer
		Area() float64
		Scale(f float64) Shape
	}
	Number interface {
		~int | ~float64
	}
	Celsius = float64
)

type List[T any] struct {
	head *node[T]
}

type node[T any] struct {
	v    T
	next *node[T]
}

func (l *List[T]) Push(v T) { l.head = &node[T]{v: v, next: l.head} }

func (l List[T]) Len() int {
	n := 0
	for x := l.head; x != nil; x = x.next {
		n++
	}
	return n
}

func (Point) Origin() Point { return Point{} }

func Map[T, U any](xs []T, f func(T) U) []U {
	out := make([]U, 0, len(xs))
	for _, x := range xs {
		out = append(out, f(x))
	}
	return out
}

var handler = func(s string) string {
	return "{" + s + "}"
}

func external(x int) int

func init() {}

func init() {}
