// Live read-only UI/preview checks. Final create requests are intercepted/aborted.
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require(process.env.PORTAL_PLAYWRIGHT_PATH || 'playwright');
const root='/home/nagi/my-bench',origin='http://dev.localhost:8000';
function python(code){return execFileSync(root+'/env/bin/python',['-c',`import frappe,json,hashlib
frappe.init(site='dev.localhost',sites_path='${root}/sites');frappe.connect();frappe.set_user('Administrator')
${code}
frappe.destroy()`],{cwd:root+'/sites',encoding:'utf8'}).trim();}
const fingerprint=()=>python(`rows={dt:frappe.get_all(dt,fields=['name','modified','docstatus'],order_by='name') for dt in ['Vehicle Master','Vehicle Import File','Purchase Receipt','Purchase Receipt Item','Landed Cost Voucher','GL Entry','Stock Ledger Entry']}
rows.update({dt:frappe.get_all(dt,fields=['name','modified','docstatus'],order_by='name') for dt in ['Stock Reconciliation','Stock Reconciliation Item','Serial and Batch Bundle','Serial and Batch Entry']})
print(hashlib.sha256(frappe.as_json(rows).encode()).hexdigest())`);
const before=fingerprint();
const seed=JSON.parse(python(`from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
frappe.local.request=Request(EnvironBuilder(path='/').get_environ());frappe.local.request_ip='127.0.0.1'
from frappe.sessions import Session
s=Session(user='Administrator',user_type='System User');frappe.db.commit()
rows=frappe.db.sql("""select vm.name,vm.vin,vm.vehicle_import_file,vm.company,pri.qty from \u0060tabVehicle Master\u0060 vm
join \u0060tabVehicle Import File\u0060 vif on vif.name=vm.vehicle_import_file
join \u0060tabPurchase Receipt\u0060 pr on pr.name=vm.purchase_receipt
join \u0060tabPurchase Receipt Item\u0060 pri on pri.name=vm.purchase_receipt_item
where vm.disabled=0 and pr.docstatus=1 and pr.is_return=0 and vif.status not in ('Completed','Cancelled') order by pri.qty""",as_dict=True)
from an_truck_portal.single_truck_cost import _target
many=next(r for r in rows if r.qty>1 and _target(frappe.get_doc('Vehicle Import File',r.vehicle_import_file),r.name)[0]['eligible'])
one=next(r for r in rows if r.qty==1 and r.vehicle_import_file!=many.vehicle_import_file)
print(json.dumps({'sid':s.sid,'one':one,'many':many,'account':frappe.db.get_value('Company',one.company,'default_expense_account'),
 'many_account':frappe.db.get_value('Company',many.company,'default_expense_account')}))`));
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addCookies([{name:'sid',value:seed.sid,domain:'dev.localhost',path:'/'}]);
 const page=await context.newPage(),errors=[],attempts=[];
 let staleConfirmation=false;
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/method/an_truck_portal.api.import_file.create_single_truck_cost*',route=>{
  attempts.push(route.request().postDataJSON());
  if(staleConfirmation)return route.fulfill({status:417,json:{exc_type:'ValidationError',_server_messages:JSON.stringify([JSON.stringify({message:'Cost details changed. Review the confirmation again.'})])}});
  return route.abort('failed');
 });
 const wait=method=>{const pending=page.waitForResponse(r=>r.url().includes(method));pending.catch(()=>{});return pending;};
 const dictionaries={ar:require('../src/locales/ar.json'),en:require('../src/locales/en.json')};
 try{
  for(const lang of ['ar','en']){
   const t=k=>dictionaries[lang][k]||k;
   await page.addInitScript(v=>localStorage.setItem('an-truck-language',v),lang);
   await page.goto(origin+'/an-truck-portal/import-files/'+encodeURIComponent(seed.one.vehicle_import_file));
   const open=page.getByRole('button',{name:t('Add Cost to One Truck'),exact:true});await open.first().waitFor();
   assert.equal(await open.count(),2);
   // Existing bulk modal remains available and retains its original fields.
   await page.getByRole('button',{name:t('Add Import Cost'),exact:true}).click();
   const bulk=page.locator('dialog[open]').filter({has:page.getByText(t('Allocation Basis'),{exact:true})});
   await bulk.waitFor();await bulk.getByRole('button',{name:t('Cancel'),exact:true}).click();
   await open.first().click();
   const dialog=page.locator('dialog.single-truck-cost-dialog[open]');
   const targetResponse=wait('get_single_truck_cost_target');
   await dialog.getByLabel(t('VIN / Chassis Number')).fill(seed.one.name);
   let response=await targetResponse;assert.equal(response.status(),200,await response.text());
   assert.equal((await response.json()).message.eligible,true);
   await dialog.getByLabel(t('Cost Amount')).fill('50');
   await dialog.getByLabel(t('Expense Account')).selectOption(seed.account);
   await dialog.getByLabel(t('Description'),{exact:true}).fill('Read-only UI preview / معاينة فقط');
   const previewResponse=wait('preview_single_truck_cost');
   await dialog.getByRole('button',{name:t('Review Cost'),exact:true}).click();
   response=await previewResponse;assert.equal(response.status(),200,await response.text());
   const preview=(await response.json()).message;
   assert.equal(preview.summary.vin,seed.one.vin);assert.equal(preview.summary.amount,50);
   await dialog.getByRole('heading',{name:t('Confirm Single-Truck Cost'),exact:true}).waitFor();
   await page.screenshot({path:`/tmp/single-truck-cost-${lang}.png`});
   await page.setViewportSize({width:390,height:844});
   const bounds=await dialog.boundingBox(),footer=await dialog.locator('.dialog-actions').boundingBox();
   assert.ok(bounds.x>=0&&bounds.y>=0&&bounds.x+bounds.width<=391&&bounds.y+bounds.height<=845);
   assert.ok(footer.y+footer.height<=845);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.screenshot({path:`/tmp/single-truck-cost-${lang}-mobile.png`});
   await page.setViewportSize({width:1440,height:1000});
   // Simulate a lost response without creating any real voucher. Retrying
   // must use exactly the same persistent backend idempotency request key.
   const start=attempts.length;
   await dialog.getByRole('button',{name:t('Confirm and Submit'),exact:true}).click();
   await dialog.getByRole('alert').waitFor();
   await dialog.getByRole('button',{name:t('Confirm and Submit'),exact:true}).click();
   await dialog.getByRole('alert').waitFor();
   await page.waitForFunction(()=>!document.querySelector('dialog.single-truck-cost-dialog[open] button[type=submit]').disabled);
   assert.equal(attempts.length,start+2);assert.deepEqual(attempts[start],attempts[start+1]);
   staleConfirmation=true;
   await dialog.getByRole('button',{name:t('Confirm and Submit'),exact:true}).click();
   await dialog.getByRole('button',{name:t('Review Cost'),exact:true}).waitFor();
   assert.equal(await dialog.getByLabel(t('Cost Amount')).isDisabled(),false);
   staleConfirmation=false;
   await dialog.getByRole('button',{name:t('Cancel'),exact:true}).click();
   // A truck outside this file cannot be selected even by typing its exact VIN.
   await open.first().click();
   const foreign=wait('get_single_truck_cost_target');
   await dialog.getByLabel(t('VIN / Chassis Number')).fill(seed.many.name);
   assert.equal((await foreign).status(),403);
   await dialog.getByRole('alert').waitFor();
   assert.equal(await dialog.getByRole('button',{name:t('Review Cost'),exact:true}).isDisabled(),true);
   await dialog.getByRole('button',{name:t('Cancel'),exact:true}).click();
   await page.goto(origin+'/an-truck-portal/import-files/'+encodeURIComponent(seed.many.vehicle_import_file));
   await page.getByRole('button',{name:t('Add Cost to One Truck'),exact:true}).first().click();
   const shared=wait('get_single_truck_cost_target');
   await dialog.getByLabel(t('VIN / Chassis Number')).fill(seed.many.name);
   const target=(await (await shared).json()).message;assert.equal(target.eligible,true);
   assert.equal(target.doctype,'Stock Reconciliation');
   await dialog.getByText(t('Stock Reconciliation'),{exact:true}).waitFor();
   await dialog.getByLabel(t('Cost Amount')).fill('5000');
   await dialog.getByLabel(t('Expense Account')).selectOption(seed.many_account);
   const serialPreview=wait('preview_single_truck_cost');
   await dialog.getByRole('button',{name:t('Review Cost'),exact:true}).click();
   response=await serialPreview;assert.equal(response.status(),200,await response.text());
   const serial=(await response.json()).message.summary;
   assert.equal(serial.doctype,'Stock Reconciliation');assert.equal(serial.amount,5000);
   assert.equal(serial.new_valuation,serial.current_valuation+5000);
   await dialog.getByRole('heading',{name:t('Confirm Single-Truck Cost'),exact:true}).waitFor();
   await page.screenshot({path:`/tmp/single-truck-cost-${lang}-shared-row.png`});
   await page.setViewportSize({width:390,height:844});
   const serialBounds=await dialog.boundingBox();
   assert.ok(serialBounds.x>=0&&serialBounds.y>=0&&serialBounds.x+serialBounds.width<=391&&serialBounds.y+serialBounds.height<=845);
   await page.screenshot({path:`/tmp/single-truck-cost-${lang}-shared-row-mobile.png`});
   await page.setViewportSize({width:1440,height:1000});
   await dialog.getByRole('button',{name:t('Cancel'),exact:true}).click();
   // Native postings/detail data are covered by rollback integration tests.
   // Render the new read-only detail route with a fixture response only.
   const detailPattern='**/api/method/an_truck_portal.api.import_file.get_single_truck_revaluation*';
   const detailName='UI-READONLY-SERIAL-REVALUATION';
   await page.route(detailPattern,route=>route.fulfill({json:{message:{...serial,name:detailName,docstatus:1,
    requested_amount:5000,previous_valuation:serial.current_valuation,quantity:1}}}));
   await page.goto(origin+'/an-truck-portal/serial-revaluations/'+detailName);
   await page.getByRole('heading',{name:detailName,exact:true}).waitFor();
   await page.getByRole('heading',{name:t('Serial Valuation Adjustment'),exact:true}).waitFor();
   assert.ok((await page.getByRole('link',{name:t('Open in Desk'),exact:true}).getAttribute('href')).includes('/stock-reconciliation/'));
   await page.screenshot({path:`/tmp/single-truck-cost-${lang}-detail.png`});
   await page.setViewportSize({width:390,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.screenshot({path:`/tmp/single-truck-cost-${lang}-detail-mobile.png`});
   await page.setViewportSize({width:1440,height:1000});
   await page.unroute(detailPattern);
  }
  assert.deepEqual(errors,[]);assert.equal(fingerprint(),before);
  console.log(JSON.stringify({arabicRTL:'passed',englishLTR:'passed',mobile:'passed',existingBulkDialog:'passed',nativeLCVPreview:'passed',foreignVINBlocked:'passed',sharedRowSerialRevaluationPreview:'passed',readOnlyDetailRoute:'passed (fixture response)',retryKeyStable:'passed',staleConfirmationReview:'passed',businessRecordsUnchanged:'passed',pageErrors:errors}));
 }catch(e){await page.screenshot({path:'/tmp/single-truck-cost-failure.png'});throw e;}
 finally{await context.request.get(origin+'/api/method/logout').catch(()=>{});await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
