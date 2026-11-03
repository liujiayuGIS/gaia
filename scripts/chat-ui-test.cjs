// Uses synthetic fixtures and in-page clipboard/speech doubles. Native copying
// is independently checked by the real Electron desktop smoke suite.
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(path.resolve(__dirname,'../desktop/node_modules/playwright'));
const base=process.env.BASE_URL||'http://127.0.0.1:8774',output=path.resolve(__dirname,'../outputs/chat-ui');
(async()=>{
 fs.mkdirSync(output,{recursive:true});const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1480,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   localStorage.setItem('gaia-session','chat-qa');
   window.__copied='';Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.__copied=text}}});
   window.__spoken=[];Object.defineProperty(window,'speechSynthesis',{value:{getVoices:()=>[{name:'QA local voice',lang:'zh-CN',localService:true}],addEventListener(){},removeEventListener(){},speak(u){window.__spoken.push(u.text)},cancel(){}}});
   window.SpeechSynthesisUtterance=class{constructor(text){this.text=text}};
  });
  const layers=await(await page.request.get(base+'/api/layers')).json(),source=await(await page.request.get(base+'/api/runs/chat-fixture-11')).json();
  await page.request.patch(base+'/api/runs/chat-fixture-11/feedback',{data:{value:null}});
  await page.goto(base);await page.locator('[data-run-id="chat-fixture-11"] .message-actions').first().waitFor();
  if(await page.getByRole('button',{name:'显示更早的消息',exact:true}).isVisible())await page.getByRole('button',{name:'显示更早的消息',exact:true}).click();
  const turn=()=>page.locator('[data-run-id="chat-fixture-11"]'),user=()=>turn().getByRole('group',{name:'提问操作'}),answer=()=>turn().getByRole('group',{name:'回答操作'}),input=()=>page.getByLabel('自然语言任务');
  assert.equal(await turn().locator('.message-markdown h2').innerText(),'界面验收样例');
  assert.equal(await turn().locator('.message-table tbody tr').count(),1);
  assert.equal(await page.evaluate(()=>window.__bad),undefined);
  assert.equal(await turn().locator('a[href^="javascript:"]').count(),0);
  assert(await user().locator('time').count());assert(await answer().locator('time').count());
  await user().getByRole('button',{name:'复制提问',exact:true}).click();assert.equal(await page.evaluate(()=>window.__copied),source.message_input);
  await answer().getByRole('button',{name:'复制回答',exact:true}).click();
  const plain=await page.evaluate(()=>window.__copied);assert(plain.includes('合成样例')&&plain.includes('print("GAIA")'));assert(!plain.includes('复制代码')&&!plain.includes('##')&&!plain.includes('**'));
  await turn().getByRole('button',{name:'复制代码',exact:true}).click();assert.equal(await page.evaluate(()=>window.__copied),'print("GAIA")');
  await answer().getByRole('button',{name:'更多回答操作',exact:true}).click();
  await page.getByRole('button',{name:'复制 Markdown',exact:true}).click();assert.equal(await page.evaluate(()=>window.__copied),source.message);
  await answer().getByRole('button',{name:'更多回答操作',exact:true}).click();
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'导出本轮对话',exact:true}).click()]);
  await download.saveAs(path.join(output,'dialogue.md'));assert(fs.readFileSync(path.join(output,'dialogue.md'),'utf8').includes(source.message));
  await input().fill('原来的草稿');await user().getByRole('button',{name:'编辑为新提问',exact:true}).click();assert.equal(await input().inputValue(),source.message_input);
  await page.getByRole('button',{name:'取消引用或编辑',exact:true}).click();assert.equal(await input().inputValue(),'原来的草稿');
  await answer().getByRole('button',{name:'引用回复',exact:true}).click();assert.equal(await input().inputValue(),'原来的草稿');
  await page.screenshot({path:path.join(output,'reply.png')});
  await input().fill('列出图层');
  let response;[response]=await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===base+'/api/runs'),page.getByRole('button',{name:'发送任务',exact:true}).click()]);
  const submitted=await response.json();assert(response.ok());
  await settled(submitted.id);const quoted=await(await page.request.get(base+'/api/runs/'+submitted.id)).json();assert.equal(quoted.reply_to.run_id,source.id);assert.equal(quoted.reply_to.role,'assistant');
  await user().getByRole('button',{name:'编辑为新提问',exact:true}).click();await input().fill('列出图层');
  [response]=await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===base+'/api/runs'),page.getByRole('button',{name:'发送新任务',exact:true}).click()]);
  const edited=await response.json();await settled(edited.id);assert.equal((await(await page.request.get(base+'/api/runs/'+edited.id)).json()).edit_of,source.id);
  assert.equal((await(await page.request.get(base+'/api/runs/'+source.id)).json()).message_input,source.message_input);
  await answer().getByRole('button',{name:'赞同回答',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[data-run-id="chat-fixture-11"] [aria-label="赞同回答"]')?.getAttribute('aria-pressed')==='true');
  await page.reload();await page.waitForFunction(()=>document.querySelector('[data-run-id="chat-fixture-11"] [aria-label="赞同回答"]')?.getAttribute('aria-pressed')==='true');
  await answer().getByRole('button',{name:'朗读回答',exact:true}).click();assert((await page.evaluate(()=>window.__spoken.join(''))).includes('合成样例'));
  await answer().getByRole('button',{name:'停止朗读',exact:true}).click();
  [response]=await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===base+'/api/runs'),answer().getByRole('button',{name:'重新回答',exact:true}).click()]);
  const rewritten=await response.json();await settled(rewritten.id);const result=await(await page.request.get(base+'/api/runs/'+rewritten.id)).json();
  assert.equal(result.reanswer_of,source.id);assert.deepEqual(result.steps,[]);assert.equal(result.validation.scope,'只读回答，没有重新执行 GIS 任务。');
  assert.deepEqual(await(await page.request.get(base+'/api/layers')).json(),layers);
  await turn().locator('.message-markdown').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'desktop.png')});
  await page.getByRole('button',{name:'外观设置',exact:true}).click();await page.getByRole('button',{name:'深色',exact:true}).click();
  await page.screenshot({path:path.join(output,'dark.png')});
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'GAIA 助手',exact:true}).click();await answer().getByRole('button',{name:'更多回答操作',exact:true}).click();
  const menu=await page.locator('.message-more-items:popover-open').boundingBox();assert(menu.x>=0&&menu.x+menu.width<=390&&menu.y>=0&&menu.y+menu.height<=844);
  await page.keyboard.press('Escape');assert.equal(await page.locator('.message-more-items:popover-open').count(),0);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));await page.screenshot({path:path.join(output,'mobile.png')});
  assert.deepEqual(errors,[]);const report={passed:true,checks:['markdown-rendering','untrusted-html-and-links-filtered','question-copy','answer-plain-copy','code-copy','markdown-copy','dialogue-download','quote-reference-submit','edit-new-task','cancel-restores-draft','feedback-persists','read-only-reanswer-no-GIS','local-speech-controls-mocked','more-popover-keyboard-and-mobile','theme-and-width']};
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
  async function settled(id){const r=await page.evaluate(async id=>{const deadline=Date.now()+30000;while(Date.now()<deadline){const value=await(await fetch('/api/runs/'+id)).json();if(!['queued','running'].includes(value.status))return value;await new Promise(r=>setTimeout(r,100))}throw new Error('Run did not settle')},id);assert.equal(r.status,'completed',r.message);await page.waitForFunction(()=>document.querySelector('.statusbar')?.textContent.includes('就绪'))}
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
