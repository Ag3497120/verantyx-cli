//! Continuous measures of what an injection did to a generation.
//!
//! The binary heuristic these replace — "ran to full length and had at least
//! half as many distinct ids as tokens" — could not resolve a band edge, and
//! said so by producing a non-monotonic sweep: at three stacked injections
//! alpha 0.05 failed while 0.1 passed. Sixteen greedy tokens either fall into a
//! loop or do not, and a threshold on a coin flip is not a measurement.
//!
//! The deeper problem is that one flag was being asked to answer two different
//! questions at once. An injection can do three distinct things, and telling
//! them apart is the entire point:
//!
//!   nothing    output identical (or near) to the baseline — inert
//!   steering   output differs but stays well-formed — the useful regime
//!   collapse   output degenerates into repetition — too strong
//!
//! "Healthy: yes/no" cannot separate the first from the second, which is how a
//! completely inert single-position injection previously read as a wide safe
//! band all the way to alpha 1.0. Two continuous quantities can:
//!
//!   `distinct2`  repetition, the standard degeneration measure. Natural
//!                continuations sit high; loops collapse toward zero.
//!   `divergence` how far the output moved from the baseline, normalised.
//!
//! Read together they give a curve rather than a cliff: divergence should rise
//! with alpha while distinct2 holds, and the band ends where distinct2 starts
//! falling. No logits needed, which matters because the generation FFI returns
//! only token ids.

/// Measured properties of one generated sequence.
#[derive(Debug, Clone, Copy)]
pub struct GenQuality {
    /// Unique tokens / total. Crude but catches total collapse.
    pub distinct1: f32,
    /// Unique bigrams / total bigrams. The repetition measure that matters:
    /// a sequence can use many distinct tokens and still cycle through them.
    pub distinct2: f32,
    /// Longest run of one repeated token.
    pub max_run: usize,
    /// Shortest detected cycle length, if the tail is periodic.
    pub loop_period: Option<usize>,
    /// Normalised edit distance from the baseline, 0 (identical) to 1.
    pub divergence: f32,
    pub len: usize,
}

impl GenQuality {
    /// Whether this looks like a well-formed continuation.
    ///
    /// The 0.6 threshold on `distinct2` is a starting point taken from the
    /// degeneration literature's usual range rather than tuned here, and it is
    /// deliberately the *only* threshold: everything else is reported as a
    /// number so a sweep can be read as a curve instead of a verdict.
    pub fn coherent(&self) -> bool {
        self.distinct2 >= 0.6 && self.loop_period.is_none() && self.max_run < 4
    }

    /// Did the injection change anything at all?
    pub fn steered(&self) -> bool { self.divergence > 0.0 }
}

pub fn measure(out: &[u32], baseline: &[u32]) -> GenQuality {
    GenQuality {
        distinct1: distinct_n(out, 1),
        distinct2: distinct_n(out, 2),
        max_run: max_run(out),
        loop_period: loop_period(out),
        divergence: normalised_edit_distance(out, baseline),
        len: out.len(),
    }
}

fn distinct_n(v: &[u32], n: usize) -> f32 {
    if v.len() < n { return 1.0; }
    let total = v.len() - n + 1;
    let mut seen: Vec<&[u32]> = Vec::with_capacity(total);
    for w in v.windows(n) {
        if !seen.contains(&w) { seen.push(w); }
    }
    seen.len() as f32 / total as f32
}

fn max_run(v: &[u32]) -> usize {
    let mut best = 0;
    let mut cur = 0;
    let mut prev: Option<u32> = None;
    for &t in v {
        if Some(t) == prev { cur += 1; } else { cur = 1; prev = Some(t); }
        if cur > best { best = cur; }
    }
    best
}

/// Shortest period p such that the last `2p` tokens are two identical blocks.
///
/// Deliberately looks at the tail only: a generation that starts well and then
/// falls into a cycle has still degenerated, and averaging over the whole
/// sequence would hide it.
fn loop_period(v: &[u32]) -> Option<usize> {
    let n = v.len();
    for p in 1..=(n / 2) {
        if n < 2 * p { break; }
        let tail = &v[n - 2 * p..];
        if tail[..p] == tail[p..] { return Some(p); }
    }
    None
}

/// Levenshtein over token ids, divided by the longer length.
///
/// Edit distance rather than "position of first difference" because two
/// sequences that diverge at token 3 and then re-converge are much closer than
/// two that diverge at 3 and never meet again, and the band question is about
/// how far the output actually moved.
fn normalised_edit_distance(a: &[u32], b: &[u32]) -> f32 {
    if a.is_empty() && b.is_empty() { return 0.0; }
    let (n, m) = (a.len(), b.len());
    let mut prev: Vec<usize> = (0..=m).collect();
    let mut cur = vec![0usize; m + 1];
    for i in 1..=n {
        cur[0] = i;
        for j in 1..=m {
            let cost = if a[i - 1] == b[j - 1] { 0 } else { 1 };
            cur[j] = (prev[j] + 1).min(cur[j - 1] + 1).min(prev[j - 1] + cost);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[m] as f32 / n.max(m) as f32
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn separates_the_three_outcomes() {
        let base = vec![1, 2, 3, 4, 5, 6, 7, 8];

        // inert: identical to baseline
        let inert = measure(&base, &base);
        assert!(inert.coherent());
        assert!(!inert.steered());

        // steering: different but well-formed
        let steered = measure(&[1, 2, 9, 4, 5, 6, 7, 8], &base);
        assert!(steered.coherent());
        assert!(steered.steered());

        // collapse: repetition
        let collapsed = measure(&[1, 2, 1, 2, 1, 2, 1, 2], &base);
        assert!(!collapsed.coherent());
        assert_eq!(collapsed.loop_period, Some(2));

        // collapse: one token repeated
        let flat = measure(&[7, 7, 7, 7, 7, 7, 7, 7], &base);
        assert!(!flat.coherent());
        assert!(flat.max_run >= 4);
    }
}
