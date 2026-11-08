// Live list/XLSX check. Only uniquely marked import-file masters are created/deleted.
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require(process.env.PORTAL_PLAYWRIGHT_PATH || 'playwright');
const root='/home/nagi/my-bench',origin='http://dev.localhost:8000';
const marker='Import Excel UI '+Date.now();
function python(code){return execFileSync(root+'/env/bin/python',['-c',`import frappe,json
frappe.init(site='dev.localhost',sites_path='${root}/sites')
frappe.connect()
frappe.set_user('Administrator')
${code}
frappe.destroy()`],{cwd:root+'/sites',encoding:'utf8'}).trim();}
const dictionaries={ar:require('../src/locales/ar.json'),en:require('../src/locales/en.json')};
const session=JSON.parse(execFileSync(root+'/env/bin/python',['-c',`import frappe,json
frappe.init(site='dev.localhost',sites_path='${root}/sites')
frappe.connect()
frappe.set_user('Administrator')
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request
frappe.local.request=Request(EnvironBuilder(path='/').get_environ())
frappe.local.request_ip='127.0.0.1'
from frappe.sessions import Session
s=Session(user='Administrator',user_type='System User')
frappe.db.commit()
print(json.dumps({'sid':s.sid,'company':frappe.defaults.get_global_default('company'),'supplier':frappe.db.get_value('Supplier',{'disabled':0},'name')}))
frappe.destroy()`],{cwd:root+'/sites',encoding:'utf8'}));
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addCookies([{name:'sid',value:session.sid,domain:'dev.localhost',path:'/'}]);
 const page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 // Exercise the real API's pagination with existing data; never fake totals/rows.
 await page.route('**/api/method/an_truck_portal.api.records.list_records?**',route=>{
  const url=new URL(route.request().url());
  if(url.searchParams.get('doctype')==='Vehicle Import File')url.searchParams.set('page_length','2');
  return route.continue({url:url.toString()});
 });
 const response=()=>{
  const pending=page.waitForResponse(r=>r.url().includes('api.records.list_records')&&r.request().method()==='GET');
  pending.catch(()=>{});return pending;
 };
 const exactName=name=>new RegExp('^\\s*'+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s*$');
 try{
  for(const lang of ['ar','en']){
   const t=key=>dictionaries[lang][key]||key;
   await page.addInitScript(value=>localStorage.setItem('an-truck-language',value),lang);
   let loading=response();await page.goto(origin+'/an-truck-portal/import-files');
   let result=await loading;assert.equal(result.status(),200,await result.text());
   let data=(await result.json()).message;
   const company=page.locator('.company-picker select');
   await company.waitFor();
   if(await company.inputValue()!==session.company){loading=response();await company.selectOption(session.company);result=await loading;data=(await result.json()).message;}
   const table=page.locator('.page > .panel.table-wrap > table');
   await table.waitFor();
   assert.equal(await page.locator('html').getAttribute('dir'),lang==='ar'?'rtl':'ltr');
   const headers=['Name','Supplier','Received Vehicles','Sold Vehicles','Remaining Vehicles','Purchase Value (Invoice Currency)','Paid Amount (Invoice Currency)','Outstanding Amount (Invoice Currency)','Status','Country of Origin','Supplier Currency','Purchase Value (SAR)','Paid Amount (SAR)','Outstanding Amount (SAR)'].map(t);
   assert.deepEqual(await table.locator('thead th').allTextContents(),headers);
   assert.ok(data.rows.length&&data.total>2,'Existing dev imports are needed for the live pagination check');
   for(const [index,key] of ['received_vehicles','sold_vehicles','remaining_vehicles'].entries()){
    assert.equal((await table.locator('tbody tr').first().locator('td').nth(index+2).textContent()).trim(),String(data.rows[0][key]??'—'));
   }
   for(const row of data.rows)assert.equal(row.remaining_vehicles,row.received_vehicles-row.sold_vehicles);
   for(const [index,key] of [[5,'purchase_value_invoice_currency'],[6,'paid_amount_invoice_currency'],[7,'outstanding_amount_invoice_currency'],[11,'purchase_value_sar'],[12,'paid_amount_sar'],[13,'outstanding_amount_sar']]){
    const money=await table.locator('tbody tr').first().locator('td').nth(index).textContent();
    for(const value of data.rows[0][key] || [])assert.ok(money.includes(value.currency));
   }
   const firstNames=data.rows.map(row=>row.name);
   loading=response();await page.getByRole('button',{name:t('Next'),exact:true}).click();
   data=(await (await loading).json()).message;
   await table.locator('tbody tr td:first-child').filter({hasText:exactName(data.rows[0].name)}).waitFor();
   assert.ok(data.rows.every(row=>!firstNames.includes(row.name)));
   const search=page.locator('.page-head input.filter');
   const name=data.rows[0].name;
   loading=response();await search.fill(name);
   data=(await (await loading).json()).message;
   assert.ok(data.rows.some(row=>row.name===name));
   await table.locator('tbody tr td:first-child').filter({hasText:exactName(name)}).waitFor();
   const downloadPromise=page.waitForEvent('download');
   await page.getByRole('button',{name:t('Export Excel'),exact:true}).click();
   const exported=await downloadPromise;const exportPath=`/tmp/import-export-${lang}.xlsx`;await exported.saveAs(exportPath);
   const sheet=JSON.parse(python(`from openpyxl import load_workbook
b=load_workbook(${JSON.stringify(exportPath)})
print(json.dumps({'headers':list(next(b.active.values)),'rows':b.active.max_row-1},ensure_ascii=False))
b.close()`));
   assert.deepEqual(sheet.headers,headers);assert.equal(sheet.rows,data.total);
   await page.screenshot({path:`/tmp/import-file-list-${lang}.png`});
   await page.setViewportSize({width:390,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.screenshot({path:`/tmp/import-file-list-${lang}-mobile.png`});
   loading=response();await search.fill('NO-MATCH-'+Date.now());
   data=(await (await loading).json()).message;assert.equal(data.total,0);
   await table.getByText(t('No records found'),{exact:true}).waitFor();
   await page.setViewportSize({width:1440,height:1000});
   await page.getByRole('button',{name:t('Import Excel'),exact:true}).click();
   const dialog=page.locator('dialog.import-excel-dialog[open]');
   await page.screenshot({path:`/tmp/import-file-excel-${lang}.png`});
   await page.setViewportSize({width:390,height:844});
   const bounds=await dialog.boundingBox();
   assert.ok(bounds.x>=0&&bounds.y>=0&&bounds.x+bounds.width<=391&&bounds.y+bounds.height<=845);
   const actions=await dialog.locator('.dialog-actions').boundingBox();
   assert.ok(actions.y+actions.height<=845,'Import actions must remain visible on mobile');
   await page.screenshot({path:`/tmp/import-file-excel-${lang}-mobile.png`});
   await page.setViewportSize({width:1440,height:1000});
   const templatePromise=page.waitForEvent('download');
   await dialog.getByRole('button',{name:t('Download Template'),exact:true}).click();
   const template=await templatePromise;await template.saveAs(`/tmp/import-template-${lang}.xlsx`);
   const validPath=`/tmp/import-valid-${lang}.xlsx`,invalidPath=`/tmp/import-invalid-${lang}.xlsx`;
   python(`from pathlib import Path
from frappe.utils.xlsxutils import make_xlsx
from an_truck_portal.api.import_file_excel import FIELDS
for filename,supplier in [(${JSON.stringify(validPath)},${JSON.stringify(session.supplier)}),(${JSON.stringify(invalidPath)},'NO-SUPPLIER')]:
 Path(filename).write_bytes(make_xlsx([list(FIELDS.values()),[${JSON.stringify('00-'+marker+'-'+lang)},supplier,'China','SAR',1,1,${JSON.stringify(marker)}]],'Import').getvalue())`);
   const apiResponse=()=>page.waitForResponse(r=>r.url().includes('import_file_excel.import_rows'));
   await dialog.locator('input[type=file]').setInputFiles(invalidPath);
   let validating=apiResponse();await dialog.getByRole('button',{name:t('Validate Rows'),exact:true}).click();
   assert.equal((await (await validating).json()).message.can_import,false);
   await dialog.getByRole('cell',{name:t('Error'),exact:true}).waitFor();
   assert.equal(await dialog.getByRole('button',{name:t('Import Validated Rows'),exact:true}).isDisabled(),true);
   await dialog.locator('input[type=file]').setInputFiles(validPath);
   validating=apiResponse();await dialog.getByRole('button',{name:t('Validate Rows'),exact:true}).click();
   assert.equal((await (await validating).json()).message.can_import,true);
   await dialog.getByRole('button',{name:t('Import Validated Rows'),exact:true}).click();
   const creating=apiResponse();
   await page.locator('dialog.confirm-dialog[open]').getByRole('button',{name:t('Import Excel'),exact:true}).click();
   const created=await creating;assert.equal(created.status(),200,await created.text());assert.equal((await created.json()).message.created,1);
   await dialog.getByRole('cell',{name:t('Created'),exact:true}).waitFor();
   await dialog.locator('.dialog-actions').getByRole('button',{name:t('Close'),exact:true}).click();
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({arabicRTL:'passed',englishLTR:'passed',fourteenColumns:'passed',liveCountsAndCurrencies:'passed',searchAndPagination:'passed',excelExportAndTemplate:'passed',excelValidationAndCreate:'passed',emptyState:'passed',mobileOverflow:'passed',pageErrors:errors}));
 }catch(error){await page.screenshot({path:'/tmp/import-file-list-failure.png'});throw error;}
 finally{
  try{python(`frappe.in_test=True
for name in frappe.get_all('Vehicle Import File',filters={'notes':${JSON.stringify(marker)}},pluck='name'):
 assert not frappe.db.exists('Vehicle Master',{'vehicle_import_file':name})
 assert not frappe.db.exists('Purchase Order',{'custom_vehicle_import_file':name})
 frappe.delete_doc('Vehicle Import File',name)
frappe.db.commit()`);}finally{await context.request.get(origin+'/api/method/logout').catch(()=>{});await browser.close();}
 }
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
