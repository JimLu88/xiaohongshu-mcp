// Invoked only by the Python-owned offline browser test. No account profile is opened.
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {prepareCommentBatch} from '../xhs_comment_batch_handoff.mjs';
const require = createRequire(import.meta.url);
const {chromium} = require('D:/AI/tachikoma/.runtime/playwright-mcp/node_modules/playwright');
const lines = createInterface({input:process.stdin});
for await (const line of lines) {
  const input=JSON.parse(line);
  const browser=await chromium.connectOverCDP(input.endpoint);
  const contexts=browser.contexts().filter(c => c.pages().some(p => p.url().includes('/explore/')));
  if(contexts.length !== 1) throw new Error('test context ambiguous');
  const result=await prepareCommentBatch(contexts[0].pages()[0],input.batch);
  process.stdout.write(JSON.stringify(result)+'\n');
  // Keep page bindings alive while Python checks user action and risk propagation.
  break;
}
process.stdin.resume();
process.stdin.once('data',()=>process.exit(0));
