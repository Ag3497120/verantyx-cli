with open("jcross_engine_glm/src/bin/test_glm.rs", "r") as f:
    content = f.read()

content = content.replace('println!("Model loaded! Running inference...");', 'println!("Model loaded! Running inference on {:?}", engine.candle_device);')

with open("jcross_engine_glm/src/bin/test_glm.rs", "w") as f:
    f.write(content)
