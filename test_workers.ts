const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');

if (isMainThread) {
    console.log("Main thread starting workers...");
    for (let i = 0; i < 2; i++) {
        const worker = new Worker(__filename, { workerData: { id: i } });
        worker.on('message', msg => console.log(`Main received: ${msg}`));
    }
} else {
    // Inside worker
    const { JCrossEngineDriver05B } = require('./src/verantyx/memory/ffi-driver-0-5b');
    console.log(`Worker ${workerData.id} loading engine...`);
    try {
        const engine = new JCrossEngineDriver05B('./qwen_0.5b_full.jgen');
        console.log(`Worker ${workerData.id} loaded engine successfully.`);
        parentPort.postMessage(`Worker ${workerData.id} done.`);
    } catch (e) {
        parentPort.postMessage(`Worker ${workerData.id} error: ${e}`);
    }
}
