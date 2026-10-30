const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||undefined,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});try{
const page=await browser.newPage();let calls=0;
await page.route('**/api/model/test',async route=>{calls++;const body=route.request().postDataJSON();if(body.model!=='gpt-5.6-sol')throw new Error('Selected model was changed');await route.fulfill({status:calls===1?400:200,contentType:'application/json',body:JSON.stringify(calls===1?{detail:'模型服务返回 HTTP 400。\n参数：reasoning_effort\n服务说明：详细错误测试'}:{ok:true,message:'连接成功：测试响应'})})});
await page.goto(process.env.BASE_URL||'http://127.0.0.1:8765');await page.getByRole('button',{name:'模型设置'}).click();await page.getByRole('button',{name:'连接模型',exact:false}).click();await page.getByLabel('API 根地址').fill('https://api.openai.com/v1');await page.getByLabel('模型名称').fill('gpt-5.6-sol');await page.getByLabel('API Key').fill('TEST_FAKE_KEY');
if(calls)throw new Error('Connection test ran without user action');
await page.getByRole('button',{name:'测试连接',exact:true}).click();await page.locator('.connection-error').waitFor();if(!(await page.locator('.connection-error').innerText()).includes('reasoning_effort'))throw new Error('Detailed error is missing');
await page.getByRole('button',{name:'测试连接',exact:true}).click();await page.locator('.connection-ok').waitFor();if(calls!==2)throw new Error('Unexpected number of API tests');
if((await page.evaluate(()=>JSON.stringify(localStorage))).includes('TEST_FAKE_KEY'))throw new Error('Secret persisted');
console.log('Provider settings UI passed: explicit test action, preserved model, detailed error, success state, key not persisted.');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
