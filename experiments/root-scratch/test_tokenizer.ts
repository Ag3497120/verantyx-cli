import { JCrossTokenizerDriver } from './src/verantyx/memory/ffi-driver';
import * as path from 'path';

const tokenizerPath = path.resolve(__dirname, 'tokenizer.json');
const tokenizer = new JCrossTokenizerDriver(tokenizerPath);

const word = tokenizer.decode(232942);
console.log(`Token 232942 decodes to: "${word}"`);

tokenizer.destroy();
