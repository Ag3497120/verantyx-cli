//! What happens to the usable strength band when several memories are injected
//! at once?
//!
//! This exists because a default was set on an untested assumption and produced
//! visibly broken output. A single injection was swept and found coherent to
//! alpha 0.3; the Swift side then shipped three memories at three neighbouring
//! layers, and the first real A/B answered with `**** ****`. Three blends is not
//! "more of a measured thing", it is a different thing that nobody had measured.
//!
//! The question worth answering is not "does N work" but which quantity governs
//! the limit:
//!
//!   - if **total** alpha across layers is what matters, the rule is a budget:
//!     divide ~0.3 by however many memories are injected
//!   - if each layer is **independent**, every memory can carry the full 0.3 and
//!     stacking is free
//!
//! Those give opposite defaults, so the sweep records the healthy band for each
//! count and then reports which model the data actually supports rather than
//! assuming one.
//!
//! Distinct vectors per slot on purpose: stacking the *same* memory three times
//! is a different experiment from three different memories, and the second is
//! the one the product does.
//!
//! Usage:  test_inject_stack <model.jgen>

use jcross_engine_glm::{jcross_engine_reset, BlendScope, InjectionSpec, JCrossEngine};

fn reset(engine: &JCrossEngine) {
    jcross_engine_reset(engine as *const JCrossEngine as *mut std::os::raw::c_void);
}

/// Same rule the single-injection sweep used, so the two are comparable:
/// ran to the requested length, and did not collapse into a few repeating ids.
fn healthy(out: &[u32], max: usize) -> bool {
    let mut v = out.to_vec();
    v.sort_unstable();
    v.dedup();
    out.len() == max && v.len() >= max / 2
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: test_inject_stack <model.jgen>");
        std::process::exit(2);
    }
    let engine = JCrossEngine::load_jgen(&args[1]).expect("load");
    let n = engine.num_layers;
    println!("model: {} layers\n", n);

    let prompt: Vec<u32> = (0..10u32).map(|i| 100 + i).collect();
    let max = 16;

    reset(&engine);
    let baseline = engine
        .execute_generation_loop(&prompt, max, None, std::ptr::null_mut())
        .expect("baseline");

    // Four distinct memories, not one repeated.
    let memories: Vec<Vec<f32>> = (0..4)
        .map(|i| {
            reset(&engine);
            let base = 500 + i * 40;
            engine
                .execute_worker_forward(&[base, base + 1, base + 2, base + 3])
                .expect("encode")
        })
        .collect();

    let start_layer = n / 3;
    let alphas = [0.05f32, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5];

    // Several prompts, because one prompt at one strength is a single sample and
    // the first version of this read a non-monotonic single-sample sweep as a
    // law. An alpha counts as healthy only if it is healthy for *every* prompt.
    let prompts: Vec<Vec<u32>> = vec![
        (0..10u32).map(|i| 100 + i).collect(),
        (0..10u32).map(|i| 900 + i).collect(),
        (0..10u32).map(|i| 2000 + i * 3).collect(),
    ];

    println!("{:<7} {:<44} {:<10} {}", "count", "healthy alphas (all prompts)",
             "contiguous", "note");
    let mut bands: Vec<(usize, f32)> = Vec::new();

    for count in 1..=4usize {
        let mut ok_list: Vec<String> = Vec::new();
        // The edge of the *contiguous* run from the bottom. Taking the last
        // healthy value instead lets an isolated island past a gap masquerade as
        // a band edge, which is precisely how 0.4 was reported as safe for two
        // injections while 0.25 and 0.3 both failed.
        let mut contiguous = 0.0f32;
        let mut still_contiguous = true;
        let mut gaps = false;

        for &alpha in alphas.iter() {
            let all_ok = prompts.iter().all(|pr| {
                let spec = InjectionSpec {
                    layer_injections: (0..count)
                        .map(|i| (start_layer + i, memories[i].clone(), alpha))
                        .collect(),
                    blend_scope: BlendScope::AllPositions,
                    ..Default::default()
                };
                reset(&engine);
                let out = engine
                    .execute_generation_loop_injected(
                        pr, max, None, std::ptr::null_mut(), Some(&spec))
                    .expect("injected");
                healthy(&out, max)
            });
            if all_ok {
                ok_list.push(format!("{}", alpha));
                if still_contiguous { contiguous = alpha; } else { gaps = true; }
            } else {
                still_contiguous = false;
            }
        }
        println!("{:<7} {:<44} {:<10} {}", count, ok_list.join(" "), contiguous,
                 if gaps { "non-monotonic — islands past a gap" } else { "" });
        bands.push((count, contiguous));
    }

    // Which quantity is actually conserved?
    println!("\ncount  band   band x count (total alpha)");
    for (c, b) in bands.iter() {
        println!("{:<6} {:<6} {:.2}", c, b, b * (*c as f32));
    }

    let totals: Vec<f32> = bands.iter().map(|(c, b)| b * (*c as f32)).collect();
    let per_layer: Vec<f32> = bands.iter().map(|(_, b)| *b).collect();
    let spread = |v: &[f32]| {
        let max = v.iter().cloned().fold(f32::MIN, f32::max);
        let min = v.iter().cloned().fold(f32::MAX, f32::min);
        if min <= 0.0 { f32::INFINITY } else { max / min }
    };
    let total_spread = spread(&totals);
    let per_spread = spread(&per_layer);

    println!("\nspread (max/min): total-alpha {:.2}x, per-layer-alpha {:.2}x",
             total_spread, per_spread);
    println!();
    // "Whichever spread is smaller wins" is not a test. Two noisy numbers always
    // have one smaller than the other, and the first version of this happily
    // declared a 2.67x spread a conserved law because the alternative was 4.00x.
    // A conserved quantity should be close to flat; anything looser than that is
    // a measurement that cannot answer the question yet, and saying so is more
    // useful than inventing a rule from it.
    const FLAT_ENOUGH: f32 = 1.5;
    if bands.iter().any(|(_, b)| *b <= 0.0) {
        println!("=> Inconclusive: at least one count had no contiguous healthy band.");
    } else if total_spread < FLAT_ENOUGH && total_spread < per_spread {
        let budget = totals.iter().sum::<f32>() / totals.len() as f32;
        println!("=> TOTAL alpha is conserved ({:.2}x spread).", total_spread);
        println!("   Rule: budget about {:.2} across all injections, i.e. alpha = {:.2} / count.",
                 budget, budget);
    } else if per_spread < FLAT_ENOUGH && per_spread < total_spread {
        let each = per_layer.iter().cloned().fold(f32::MAX, f32::min);
        println!("=> PER-LAYER alpha is conserved ({:.2}x spread).", per_spread);
        println!("   Rule: each injection may carry up to about {:.2} regardless of count.", each);
    } else {
        println!("=> INCONCLUSIVE. Neither quantity is flat (total {:.2}x, per-layer {:.2}x; \
                  flat would be under {:.1}x).", total_spread, per_spread, FLAT_ENOUGH);
        let safe = per_layer.iter().cloned().fold(f32::MAX, f32::min);
        println!("   Until this resolves, the only defensible default is the lowest band \
                  observed at any count: alpha {:.2}.", safe);
    }

    // A conserved-looking constant means nothing if injection did not change
    // anything to begin with.
    let probe = InjectionSpec {
        layer_injections: vec![(start_layer, memories[0].clone(), 0.2)],
        blend_scope: BlendScope::AllPositions,
        ..Default::default()
    };
    reset(&engine);
    let probe_out = engine
        .execute_generation_loop_injected(&prompt, max, None, std::ptr::null_mut(), Some(&probe))
        .expect("probe");
    if probe_out == baseline {
        println!("\nWARNING: injection did not change the output at all — every band above \
                  is measuring nothing.");
        std::process::exit(1);
    }
}
