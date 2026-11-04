// Live dev-only smoke test: saves uniquely marked drafts, then deletes only those drafts.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const {chromium} = require(process.env.PORTAL_PLAYWRIGHT_PATH || 'playwright');
const root='/home/nagi/my-bench', origin='http://dev.localhost:8000';
const marker=`Voucher browser test ${Date.now()}`;
const dictionaries={ar:require('../src/locales/ar.json'),en:require('../src/locales/en.json')};
function python(code){return execFileSync(root+'/env/bin/python',['-c',`import frappe,json
frappe.init(site='dev.localhost',sites_path='${root}/sites')
frappe.connect()
frappe.set_user('Administrator')
${code}
frappe.destroy()`],{cwd:root+'/sites',encoding:'utf8'}).trim();}
(async()=>{
 const session=JSON.parse(python(`from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
frappe.local.request=Request(EnvironBuilder(path='/').get_environ())
frappe.local.request_ip='127.0.0.1'
from frappe.sessions import Session
s=Session(user='Administrator',user_type='System User')
result={'sid':s.sid,'customer':frappe.db.get_value('Customer',{'disabled':0},'name'),'supplier':frappe.db.get_value('Supplier',{'disabled':0},'name'),'preference':frappe.defaults.get_user_default('an_truck_portal_language')}
frappe.db.commit()
print(json.dumps(result))`));
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addCookies([{name:'sid',value:session.sid,domain:'dev.localhost',path:'/'}]);
 const page=await context.newPage(),errors=[]; let lang='ar';
 const t=key=>dictionaries[lang][key]||key;
 const button=(scope,key)=>scope.getByRole('button',{name:t(key),exact:true});
 const field=(scope,key)=>scope.getByLabel(new RegExp('^\\s*'+t(key).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?:\\s*\\*)?\\s*$'));
 page.on('pageerror',e=>errors.push(e.message));
 fs.mkdirSync('/tmp/an-truck-vouchers',{recursive:true});
 try{
  // An unsupported browser preference must resolve to Arabic.
  await page.addInitScript(()=>localStorage.setItem('an-truck-language','fr'));
  await page.goto(origin+'/an-truck-portal/vouchers');
  await button(page,'Create Receipt Voucher').waitFor();
  assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
  for(const active of ['ar','en'])for(const direction of ['Receive','Pay']){
   lang=active;
   await page.addInitScript(value=>localStorage.setItem('an-truck-language',value),lang);
   await page.goto(origin+'/an-truck-portal/vouchers/'+(direction==='Receive'?'receipts':'payments'));
   const title=direction==='Receive'?'Create Receipt Voucher':'Create Payment Voucher';
   await button(page,title).click();
   let dialog=page.getByRole('dialog',{name:t(title),exact:true});
   await field(dialog,'Amount').fill('125.50');
   await button(dialog,'Language').click();
   lang=lang==='ar'?'en':'ar';
   dialog=page.getByRole('dialog',{name:t(title),exact:true});
   assert.equal(Number(await field(dialog,'Amount').inputValue()),125.5);
   await button(dialog,'Language').click(); lang=active;
   dialog=page.getByRole('dialog',{name:t(title),exact:true});
   assert.equal(await page.locator('html').getAttribute('dir'),lang==='ar'?'rtl':'ltr');
   const partyLabel=direction==='Receive'?'Received From':'Pay To';
   await field(dialog,partyLabel).fill(direction==='Receive'?session.customer:session.supplier);
   await field(dialog,partyLabel).dispatchEvent('change');
   await field(dialog,'Payment Method').selectOption('Cash');
   assert.ok(await field(dialog,direction==='Receive'?'Receiving Account':'Paying Account').inputValue());
   assert.equal(await field(dialog,'Currency').inputValue(),'SAR');
   const note=marker+' '+lang+' '+direction;
   await field(dialog,'Description').fill(note);
   await page.screenshot({path:`/tmp/an-truck-vouchers/${lang}-${direction.toLowerCase()}-form.png`});
   const saving=page.waitForResponse(r=>r.url().includes('vouchers.save_voucher'));
   await button(dialog,'Save Draft').click();
   const response=await saving;assert.equal(response.status(),200,await response.text());
   const name=(await response.json()).message.document.name;
   await page.waitForURL('**/vouchers/'+name);
   await button(page,'Edit Draft').click();
   const editTitle=direction==='Receive'?'Edit Receipt Voucher':'Edit Payment Voucher';
   dialog=page.getByRole('dialog',{name:t(editTitle),exact:true});
   await field(dialog,'Description').waitFor();
   await page.waitForFunction(note=>document.querySelector('dialog[open] textarea')?.value===note,note);
   assert.equal(await field(dialog,'Amount').inputValue(),'125.5');
   await button(dialog,'Cancel').click();
   await button(page,'Print').click();
   const print=page.getByRole('dialog',{name:t('Print'),exact:true});
   await page.waitForFunction(()=>document.querySelector('dialog[open] select')?.value==='AN Truck Voucher');
   await button(print,'Print Preview').click();
   const frame=page.frameLocator('iframe.print-preview-frame');
   const printTitle=lang==='ar'?(direction==='Receive'?'سند قبض':'سند صرف'):(direction==='Receive'?'RECEIPT VOUCHER':'PAYMENT VOUCHER');
   await frame.getByRole('heading',{name:printTitle,exact:true}).waitFor();
   assert.equal(await frame.locator('.truck-voucher').getAttribute('dir'),lang==='ar'?'rtl':'ltr');
   await page.screenshot({path:`/tmp/an-truck-vouchers/${lang}-${direction.toLowerCase()}-preview.png`});
   const pdf=await context.request.get(origin+'/api/method/an_truck_portal.api.vouchers.download_pdf',{params:{name,language:lang}});
   assert.equal(pdf.status(),200,await pdf.text());
   assert.ok(pdf.headers()['content-type'].startsWith('application/pdf'));
   assert.ok(pdf.headers()['content-disposition'].startsWith('attachment;'));
   const bytes=await pdf.body();assert.equal(bytes.subarray(0,4).toString(),'%PDF');
   fs.writeFileSync(`/tmp/an-truck-vouchers/${lang}-${direction.toLowerCase()}-portal.pdf`,bytes);
   await button(print,'Cancel').click();
   if(lang==='ar'&&direction==='Receive'){
    await page.setViewportSize({width:390,height:844});
    await button(page,'Edit Draft').click();
    dialog=page.getByRole('dialog',{name:t(editTitle),exact:true});
    await field(dialog,'Description').waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await dialog.locator('.dialog-body').evaluate(el=>el.scrollTop=el.scrollHeight);
    assert.equal(await dialog.locator('.dialog-head').isVisible(),true);
    assert.equal(await button(dialog,'Save Draft').isVisible(),true);
    await page.screenshot({path:'/tmp/an-truck-vouchers/ar-mobile.png'});
    await button(dialog,'Cancel').click();await page.setViewportSize({width:1440,height:1000});
   }
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({fourForms:'passed',saveEditReload:'passed',languagePreservesData:'passed',fourPrintPreviews:'passed',fourPDFDownloads:'passed',arabicMobile:'passed',pageErrors:errors}));
 }catch(e){console.error('Form errors:',await page.locator('.form-error').allTextContents());await page.screenshot({path:'/tmp/an-truck-vouchers/browser-failure.png'});throw e;}
 finally{
  try{python(`frappe.in_test=True
for name in frappe.get_all('Payment Entry',filters={'remarks':['like',${JSON.stringify(marker+'%')}],'docstatus':0},pluck='name'):
 assert not frappe.db.exists('GL Entry',{'voucher_type':'Payment Entry','voucher_no':name})
 frappe.delete_doc('Payment Entry',name)
frappe.defaults.set_user_default('an_truck_portal_language',${session.preference?JSON.stringify(session.preference):'None'},user='Administrator')
frappe.db.commit()`);}finally{await context.request.get(origin+'/api/method/logout').catch(()=>{});await browser.close();}
 }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
