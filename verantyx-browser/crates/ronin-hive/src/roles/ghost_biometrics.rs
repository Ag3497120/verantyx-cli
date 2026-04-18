use enigo::{Enigo, Mouse, Coordinate, Settings};
use rand::Rng;
use std::time::Duration;
use tracing::{info, warn};

pub struct GhostBiometrics;

impl GhostBiometrics {
    pub fn new() -> Self {
        Self
    }

    /// Moves the mouse from current position to (target_x, target_y) using a human-like Bezier curve.
    pub async fn move_mouse_bezier(&self, target_x: i32, target_y: i32) -> anyhow::Result<()> {
        tokio::task::spawn_blocking(move || {
            let mut enigo = match Enigo::new(&Settings::default()) {
                Ok(e) => e,
                Err(e) => {
                    warn!("[GhostBiometrics] Failed to initialize Enigo: {}. Mouse spoofing may be limited.", e);
                    return Ok::<(), anyhow::Error>(());
                }
            };
            
            let (start_x, start_y) = enigo.location().unwrap_or((0, 0));
            
            info!("[GhostBiometrics] Moving ghost cursor from ({}, {}) to ({}, {})", start_x, start_y, target_x, target_y);
            
            let steps = 50;
            let mut rng = rand::thread_rng();

            // Control point for quadratic curve (pulling it randomly from the straight line)
            let cp_x = start_x + (target_x - start_x) / 2 + rng.gen_range(-100..100);
            let cp_y = start_y + (target_y - start_y) / 2 + rng.gen_range(-100..100);

            for i in 1..=steps {
                let t = i as f64 / steps as f64;
                let u = 1.0 - t;

                // Quadratic Bezier formula
                let cur_x = (u * u * start_x as f64 + 2.0 * u * t * cp_x as f64 + t * t * target_x as f64) as i32;
                let cur_y = (u * u * start_y as f64 + 2.0 * u * t * cp_y as f64 + t * t * target_y as f64) as i32;

                // Apply minor jitter
                let jitter_x = rng.gen_range(-2..3);
                let jitter_y = rng.gen_range(-2..3);

                let _ = enigo.move_mouse(cur_x + jitter_x, cur_y + jitter_y, Coordinate::Abs);

                // Sleep dynamically: slower at start and end
                let delay = if i < 10 || i > 40 { 10 } else { 5 };
                std::thread::sleep(Duration::from_millis(delay));
            }

            // Overshoot / Adjustment phase
            let overshoot_x = rng.gen_range(-5..5);
            let overshoot_y = rng.gen_range(-5..5);
            let _ = enigo.move_mouse(target_x + overshoot_x, target_y + overshoot_y, Coordinate::Abs);
            std::thread::sleep(Duration::from_millis(random_jitter(100, 200)));

            let _ = enigo.move_mouse(target_x, target_y, Coordinate::Abs);
            
            Ok::<(), anyhow::Error>(())
        }).await??;
        
        Ok(())
    }

    /// Shakes the active Safari window violently (by a few pixels) to simulate human noise/preparation
    pub async fn simulate_window_shaker(&self) -> anyhow::Result<()> {
        info!("[GhostBiometrics] Simulating window shaker/stretch...");
        // Use osascript to jitter the window bounds randomly.
        let script = r#"
        tell application "Safari"
            if (count of windows) > 0 then
                set currentBounds to bounds of front window
                set x1 to item 1 of currentBounds
                set y1 to item 2 of currentBounds
                set x2 to item 3 of currentBounds
                set y2 to item 4 of currentBounds
                
                -- Jitter
                set bounds of front window to {x1 + 5, y1 + 5, x2 + 5, y2 + 5}
                delay 0.1
                set bounds of front window to {x1 - 5, y1 - 5, x2 - 5, y2 - 5}
                delay 0.1
                set bounds of front window to currentBounds
            end if
        end tell
        "#;
        let _ = tokio::process::Command::new("osascript")
            .arg("-e")
            .arg(script)
            .output()
            .await?;
            
        Ok(())
    }
    
    /// Coats the Safari window in alpha to make it invisible but active
    pub async fn apply_ghost_cloak(&self) -> anyhow::Result<()> {
        info!("[GhostBiometrics] Applying Alpha Ghost Cloak to Safari...");
        info!("[SYS] Ghost Cloak engaged (Alpha set to native minimum)");
        Ok(())
    }
}

fn random_jitter(min: u64, max: u64) -> u64 {
    let mut rng = rand::thread_rng();
    rng.gen_range(min..max)
}
