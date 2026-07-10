use ndarray::{Array1, Array2};
use rand::Rng;

pub fn optimize_thought_vector(
    w_mat: &Array2<f32>,
    x_in: &Array1<f32>,
    max_steps: usize,
    lr: f32,
    temperature: f32,
) -> (Array1<f32>, f32) {
    let mut x = x_in.clone();
    let hidden_dim = x.len();
    let mut rng = rand::thread_rng();
    
    let num_axes = 6;
    let axis_size = hidden_dim / num_axes;
    let mut locked_axes = vec![false; num_axes];
    
    let mut final_entropy = 0.0;

    for step in 0..max_steps {
        // 1. Compute logits: z = W x
        let mut z = w_mat.dot(&x);
        
        // 2. Softmax
        let max_z = z.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
        let mut p = z.mapv(|v| ((v - max_z) / temperature).exp());
        let sum_p = p.sum();
        p.mapv_inplace(|v| v / sum_p);
        
        // 3. Compute Entropy L
        let l: f32 = p.iter().map(|&pi| if pi > 1e-10 { -pi * pi.ln() } else { 0.0 }).sum();
        final_entropy = l;
        
        // Early stop if highly resonant
        if l < 0.5 {
            break;
        }

        // 4. Compute gradient w.r.t logits: g = p * (L - ln(p)) / temperature
        let g = p.mapv(|pi| if pi > 1e-10 { pi * (l - pi.ln()) / temperature } else { 0.0 });
        
        // 5. Compute gradient w.r.t x: grad_x = W^T g
        let mut grad_x = w_mat.t().dot(&g);
        
        // 6. Cascading Lock: freeze axes based on entropy milestones
        // Max entropy for 151936 vocab is ~11.9
        let lock_thresholds = [6.0, 5.0, 4.0, 3.0, 2.0, 1.0];
        for (i, &thresh) in lock_thresholds.iter().enumerate() {
            if i < num_axes && l < thresh {
                locked_axes[i] = true;
            }
        }
        
        // Apply mask to gradient
        for i in 0..num_axes {
            if locked_axes[i] {
                let start = i * axis_size;
                let end = if i == num_axes - 1 { hidden_dim } else { (i + 1) * axis_size };
                for j in start..end {
                    grad_x[j] = 0.0;
                }
            }
        }
        
        // 7. Langevin noise for unlocked axes
        for i in 0..num_axes {
            if !locked_axes[i] {
                let start = i * axis_size;
                let end = if i == num_axes - 1 { hidden_dim } else { (i + 1) * axis_size };
                for j in start..end {
                    let noise: f32 = rng.gen_range(-0.01..0.01);
                    x[j] -= lr * grad_x[j] + noise;
                }
            }
        }
    }
    
    (x, final_entropy)
}
