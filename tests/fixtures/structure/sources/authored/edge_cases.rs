#![allow(dead_code)]

//! Crate-level documentation.

use std::fmt;

/// An outer doc comment is a line_comment and must not reset attributes.
#[derive(Debug, Clone)]
// A plain comment between attributes.
#[repr(C)]
pub struct Point {
    #[doc = "x coordinate"]
    pub x: i32,
    pub y: i32,
}

pub struct Tuple(i32, i32);

// An attribute followed by a non-symbol resets the pending attribute run.
#[cfg(test)]
use std::collections::HashMap;

#[derive(Debug)]
pub enum Shape {
    Circle { radius: f64 },
    #[allow(unused)]
    Square(f64),
    Empty,
}

pub union Bits {
    int: u32,
    float: f32,
}

pub trait Area {
    type Output;
    const SIDES: usize;
    fn area(&self) -> f64;
    fn describe(&self) -> String {
        format!("{}", self.area())
    }
}

impl Area for Shape {
    type Output = f64;
    const SIDES: usize = 0;
    #[inline]
    fn area(&self) -> f64 {
        match self {
            Shape::Circle { radius } => 3.14 * radius * radius,
            Shape::Square(s) => s * s,
            Shape::Empty => 0.0,
        }
    }
}

impl<T: fmt::Debug> fmt::Display for Wrapper<T> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}", self.0)
    }
}

pub struct Wrapper<T>(T);

pub mod nested {
    pub mod inner {
        pub fn deep() -> u8 { 0 }
        pub static COUNTER: u8 = 0;
    }
    pub type Alias = u32;
    macro_rules! noop {
        () => {};
    }
}

extern "C" {
    fn abs(x: i32) -> i32;
}

const fn square(x: u32) -> u32 { x * x }

unsafe fn danger() {}

async fn fetch() -> u8 { 1 }

fn outer() {
    fn inner_helper() {}
    let closure = |x: i32| { x + 1 };
}
