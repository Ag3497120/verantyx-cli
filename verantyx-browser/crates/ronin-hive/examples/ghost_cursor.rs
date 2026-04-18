use ronin_hive::roles::ghost_biometrics::GhostBiometrics;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    println!("Initialize Ghost Biometrics...");
    let mut ghost = GhostBiometrics::new();

    println!("Shaking window to simulate Human Focus...");
    ghost.simulate_window_shaker().await?;

    println!("Moving mouse via Bezier Curve to coordinates (500, 500) over ~800ms...");
    ghost.move_mouse_bezier(500, 500).await?;

    println!("Ghost Cloak Engage!");
    ghost.apply_ghost_cloak().await?;

    println!("Completed Biometric Spoofing sequence.");

    Ok(())
}
