"""List/XLSX aggregates. All integration fixtures and postings are rolled back.

PO/vehicle parents use db_insert only to model legacy/cross-company links without
posting transactions, creating stock, or invoking operational save hooks.
"""
import hashlib
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase

from an_truck_portal.api import records


class TestImportFileList(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.previous_user = frappe.session.user
		frappe.set_user("Administrator")
		frappe.db.savepoint("import_list")
		self.before = self.fingerprint()
		self.marker = "Import list " + uuid4().hex[:10]
		self.company = frappe.defaults.get_global_default("company")
		self.supplier = frappe.db.get_value("Supplier", {"disabled":0}, "name")
		self.first = self.import_file("A")
		self.second = self.import_file("B")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="import_list")
		self.assertEqual(self.fingerprint(),self.before,"Existing records must remain unchanged")
		frappe.set_user(self.previous_user)
		super().tearDown()

	def fingerprint(self):
		rows = {dt:frappe.get_all(dt,fields=["name","modified","docstatus"],order_by="name")
			for dt in ("Vehicle Import File","Vehicle Master","Purchase Order","Purchase Receipt","Sales Invoice","Delivery Note","Purchase Invoice","Payment Entry","Payment Ledger Entry","Journal Entry","GL Entry","Stock Ledger Entry")}
		return hashlib.sha256(frappe.as_json(rows).encode()).hexdigest()

	def import_file(self, suffix, company=None):
		return frappe.get_doc({"doctype":"Vehicle Import File","import_title":self.marker+suffix,
			"company":company or self.company,"supplier":self.supplier,"supplier_currency":"SAR",
			"transaction_exchange_rate":1,"total_expected_vehicles":999}).insert()

	def order(self, suffix, import_file=None, currency="USD", amount=100, docstatus=0, company=None):
		doc = frappe.get_doc({"doctype":"Purchase Order","name":self.marker+" PO "+suffix,
			"company":company or self.company,"supplier":self.supplier,"currency":currency,
			"grand_total":amount,"base_grand_total":amount*{'USD':3.75,'EUR':4,'SAR':1}.get(currency,1),"docstatus":docstatus,
			"custom_vehicle_import_file":import_file.name if import_file else None})
		doc.db_insert()
		return doc

	def vehicle(self, suffix, import_file, order=None, company=None, disabled=0, **values):
		doc = frappe.get_doc({"doctype":"Vehicle Master","name":self.marker+" VIN "+suffix,
			"vin":self.marker+" VIN "+suffix,"company":company or import_file.company,
			"vehicle_import_file":import_file.name,"purchase_order":order.name if order else None,"disabled":disabled,**values})
		doc.db_insert()
		return doc

	def listing(self, **kwargs):
		return records.list_records("Vehicle Import File",search=self.marker,**kwargs)

	def transaction(self,doctype,suffix,items=(),docstatus=1,is_return=0,return_against=None,company=None):
		"""Read-only query fixtures; no stock/accounting hooks, always rolled back."""
		doc=frappe.get_doc({'doctype':doctype,'name':self.marker+' '+suffix,'company':company or self.company,
			'docstatus':docstatus,'is_return':is_return,'return_against':return_against})
		doc.db_insert()
		doc.set('items',[])
		for index,values in enumerate(items,1):
			row=frappe.get_doc({'doctype':doctype+' Item','parent':doc.name,'parenttype':doctype,'parentfield':'items',
				'idx':index,'docstatus':docstatus,'qty':1,**values})
			row.db_insert();doc.items.append(row)
		return doc

	def test_received_sold_remaining_use_actual_documents_and_vin_sets(self):
		receipt=self.transaction('Purchase Receipt','receipt')
		vehicles=[self.vehicle(str(i),self.first,purchase_receipt=receipt.name,vehicle_status='Received') for i in range(9)]
		v=vehicles
		# Duplicate invoice rows and stale status labels must not count a VIN twice.
		self.transaction('Sales Invoice','sold',[{'custom_vehicle_master':v[0].name}]*2)
		self.transaction('Sales Invoice','cancelled sale',[{'custom_vehicle_master':v[1].name}],docstatus=2)
		self.transaction('Sales Invoice','draft sale',[{'custom_vehicle_master':v[2].name}],docstatus=0)
		frappe.db.set_value('Vehicle Master',v[2].name,'vehicle_status','Sold')
		original=self.transaction('Sales Invoice','returned sale',[{'custom_vehicle_master':v[3].name}])
		self.transaction('Sales Invoice','credit',[{'qty':-1,'sales_invoice_item':original.items[0].name}],is_return=1,return_against=original.name)
		original=self.transaction('Sales Invoice','cancelled return sale',[{'custom_vehicle_master':v[4].name}])
		self.transaction('Sales Invoice','cancelled credit',[{'qty':-1,'custom_vehicle_master':v[4].name}],is_return=1,return_against=original.name,docstatus=2)
		original=self.transaction('Sales Invoice','partly returned invoice',[{'custom_vehicle_master':v[5].name},{'custom_vehicle_master':v[6].name}])
		self.transaction('Sales Invoice','one vehicle credit',[{'qty':-1,'custom_vin':v[5].vin}],is_return=1,return_against=original.name)
		self.transaction('Delivery Note','delivery without invoice',[{'custom_vehicle_master':v[7].name}])
		original=self.transaction('Sales Invoice','first sale',[{'custom_vehicle_master':v[8].name}])
		self.transaction('Sales Invoice','returned first sale',[{'qty':-1,'custom_vehicle_master':v[8].name}],is_return=1,return_against=original.name)
		self.transaction('Sales Invoice','resale',[{'custom_vehicle_master':v[8].name}])
		self.vehicle('disabled but received',self.first,purchase_receipt=receipt.name,disabled=1)
		self.vehicle('not yet received',self.first,vehicle_status='Ordered')
		self.vehicle('empty vin',self.first,purchase_receipt=receipt.name,vin='')
		for status in (0,2):
			invalid=self.transaction('Purchase Receipt','invalid receipt '+str(status),docstatus=status)
			self.vehicle('invalid receipt '+str(status),self.first,purchase_receipt=invalid.name)
		returned=self.transaction('Purchase Receipt','supplier return',is_return=1)
		self.vehicle('return is not a receipt',self.first,purchase_receipt=returned.name)
		other_company=frappe.db.get_value('Company',{'name':['!=',self.company]},'name')
		foreign=self.transaction('Purchase Receipt','other company receipt',company=other_company)
		self.vehicle('other company receipt',self.first,purchase_receipt=foreign.name)
		self.transaction('Sales Invoice','other company invoice',[{'custom_vehicle_master':v[1].name}],company=other_company)
		unreceived=self.vehicle('sold but unreceived',self.first)
		self.transaction('Sales Invoice','not received sale',[{'custom_vehicle_master':unreceived.name}])
		row=self.metric()
		self.assertEqual((row.received_vehicles,row.sold_vehicles,row.remaining_vehicles),(10,4,6))
		from an_truck_portal.api import import_file_excel
		from openpyxl import load_workbook
		from io import BytesIO
		import_file_excel.export(company=self.company,search=self.first.name)
		book=load_workbook(BytesIO(frappe.local.response.filecontent))
		exported=next(values for values in list(book.active.values)[1:] if values[0]==self.first.name)
		self.assertEqual(exported[2:5],(10,4,6))
		book.close()
		self.assertEqual((self.metric(self.second).received_vehicles,self.metric(self.second).sold_vehicles,self.metric(self.second).remaining_vehicles),(0,0,0))
		# Even malformed legacy duplicate VIN parents cannot multiply the counts.
		from an_truck_portal.import_file_metrics import vehicle_counts
		copies=[frappe._dict({**v[0].as_dict(),'sales_invoice':None,'delivery_note':None}),frappe._dict({**v[0].as_dict(),'name':'duplicate legacy parent','sales_invoice':None,'delivery_note':None})]
		received,sold,_=vehicle_counts({self.first.name:self.first},copies)
		self.assertEqual((len(received[self.first.name]),len(sold[self.first.name])),(1,1))

	def test_delivery_returns_only_remove_the_linked_vehicle_sale_and_allow_resale(self):
		receipt=self.transaction('Purchase Receipt','receipt')
		first,second=[self.vehicle(str(i),self.first,purchase_receipt=receipt.name) for i in range(2)]
		delivery=self.transaction('Delivery Note','original delivery',[{'custom_vehicle_master':v.name} for v in (first,second)])
		invoice=self.transaction('Sales Invoice','original invoice',[{'custom_vehicle_master':v.name,'delivery_note':delivery.name,'dn_detail':delivery.items[i].name} for i,v in enumerate((first,second))])
		self.transaction('Delivery Note','stock return',[{'qty':-1,'dn_detail':delivery.items[0].name}],is_return=1,return_against=delivery.name)
		self.transaction('Delivery Note','cancelled stock return',[{'qty':-1,'si_detail':invoice.items[1].name}],is_return=1,return_against=delivery.name,docstatus=2)
		self.assertEqual((self.metric().received_vehicles,self.metric().sold_vehicles,self.metric().remaining_vehicles),(2,1,1))
		self.transaction('Sales Invoice','new sale',[{'custom_vehicle_master':first.name}])
		self.assertEqual((self.metric().sold_vehicles,self.metric().remaining_vehicles),(2,0))

	def test_vehicle_counts_are_batched_and_permission_aware(self):
		receipt=self.transaction('Purchase Receipt','receipt')
		for index in range(25):self.vehicle(str(index),self.first,purchase_receipt=receipt.name)
		for size in (1,100):
			with patch.object(records.frappe,'get_list',wraps=frappe.get_list) as query:self.listing(page_length=size,filters={'name':self.first.name})
			calls=[call.args[0] for call in query.call_args_list]
			self.assertEqual(calls.count('Vehicle Master'),2)  # page plus one batched legacy receipt lookup
			self.assertLessEqual(calls.count('Purchase Receipt'),2)
			self.assertLessEqual(calls.count('Sales Invoice'),1)
		user=frappe.get_doc({'doctype':'User','email':uuid4().hex+'@example.test','first_name':'Receipt viewer','send_welcome_email':0,
			'roles':[{'role':'AN Truck Portal User'},{'role':'AN Truck Viewer'}]}).insert()
		frappe.set_user(user.name)
		self.assertIsNone(self.metric().received_vehicles)
		self.assertIsNone(self.metric().sold_vehicles)
		self.assertIsNone(self.metric().remaining_vehicles)

	def test_actual_count_unique_orders_company_currency_and_legacy_links(self):
		first = self.order("A",self.first,amount=100.1)
		self.order("B",self.first,amount=200.2,docstatus=1)
		self.order("EUR",self.first,currency="EUR",amount=50)
		self.order("cancelled",self.first,amount=9000,docstatus=2)
		legacy = self.order("legacy",amount=12.5)
		other = self.order("other",self.second,amount=70)
		for suffix, order in [("1",first),("2",first),("3",legacy),("4",legacy),("5",other)]:
			self.vehicle(suffix,self.first,order)
		self.vehicle("disabled",self.first,first,disabled=1)
		rows = {row.name:row for row in self.listing()["rows"]}
		self.assertEqual(rows[self.first.name].vehicle_count,6)
		self.assertEqual(rows[self.second.name].vehicle_count,0)
		self.assertEqual(rows[self.first.name].purchase_value,[{"currency":"SAR","amount":1373.0}])
		self.assertEqual(rows[self.second.name].purchase_value,[{"currency":"SAR","amount":262.5}])
		self.assertEqual(rows[self.first.name].total_expected_vehicles,999)

	def test_search_empty_results_and_real_pagination(self):
		self.import_file("C")
		first, second = self.listing(page_length=2), self.listing(page=2,page_length=2)
		self.assertEqual(first["total"],3)
		self.assertTrue(first["has_more"])
		self.assertEqual(len(first["rows"]),2)
		self.assertEqual(len(second["rows"]),1)
		self.assertFalse(second["has_more"])
		self.assertFalse({row.name for row in first["rows"]}&{row.name for row in second["rows"]})
		empty = records.list_records("Vehicle Import File",search=uuid4().hex)
		self.assertEqual((empty["rows"],empty["total"]),([],0))
		self.assertTrue(all(row.purchase_value==[{"currency":"SAR","amount":0.0}] and row.vehicle_count==0 for row in first["rows"]))

	def test_shared_legacy_order_is_not_counted_again_on_another_page(self):
		order=self.order('shared legacy',currency='SAR',amount=100)
		self.vehicle('shared A',self.first,order)
		self.vehicle('shared B',self.second,order)
		for page in (1,2):
			row=self.listing(page=page,page_length=1)['rows'][0]
			self.assertEqual(row.vehicle_count,1)
			self.assertIsNone(row.purchase_value)
			self.assertIsNone(row.paid_amount)
			self.assertEqual(row._finance_issue,'Shared documents require an explicit import-file link.')

	def test_batch_queries_do_not_grow_with_page_size(self):
		for index in range(25):
			order = self.order(str(index),self.first,amount=2)
			self.vehicle(str(index),self.first,order)
		for size in (1,100):
			with patch.object(records.frappe,"get_list",wraps=frappe.get_list) as query:
				result = self.listing(page_length=size)
			self.assertEqual([c.args[0] for c in query.call_args_list].count("Vehicle Master"),1)
			self.assertEqual([c.args[0] for c in query.call_args_list].count("Purchase Order"),1)
			self.assertEqual([c.args[0] for c in query.call_args_list].count("Vehicle Import File"),2)
			if size==100:
				row = next(row for row in result["rows"] if row.name==self.first.name)
				self.assertEqual(row.vehicle_count,25)
				self.assertEqual(row.purchase_value,[{"currency":"SAR","amount":187.5}])

	def test_permissions_and_company_isolation(self):
		self.vehicle("own",self.first)
		self.order("own",self.first,amount=25)
		other_company = frappe.db.get_value("Company",{"name":["!=",self.company]},"name")
		foreign = self.import_file("other-company",company=other_company)
		self.vehicle("foreign",self.first,company=other_company)
		self.order("foreign",self.first,amount=900,company=other_company)
		self.order("other-company",foreign,amount=120,company=other_company)
		user = frappe.get_doc({"doctype":"User","email":uuid4().hex+"@example.test","first_name":"Import List Viewer",
			"send_welcome_email":0,"roles":[{"role":"AN Truck Portal User"},{"role":"AN Truck Viewer"}]}).insert()
		frappe.set_user(user.name)
		rows = {row.name:row for row in self.listing()["rows"]}
		self.assertEqual(rows[self.first.name].vehicle_count,1)
		self.assertIsNone(rows[self.first.name].purchase_value)
		frappe.set_user("Administrator")
		user.append("roles",{"role":"Purchase User"});user.save()
		frappe.set_user(user.name)
		# The installed China Truck supplier-scope hook must remain effective.
		self.assertEqual({row.name:row for row in self.listing()["rows"]}[self.first.name].purchase_value,[{"currency":"SAR","amount":0.0}])
		frappe.set_user("Administrator")
		user.append("roles",{"role":"Purchase Manager"});user.save()
		frappe.get_doc({"doctype":"User Permission","user":user.name,"allow":"Company","for_value":self.company,
			"apply_to_all_doctypes":1}).insert()
		frappe.set_user(user.name)
		rows = {row.name:row for row in self.listing()["rows"]}
		self.assertNotIn(foreign.name,rows)
		self.assertEqual(rows[self.first.name].purchase_value,[{"currency":"SAR","amount":93.75}])
		self.assertEqual(self.listing(company=other_company)["rows"],[])
		frappe.set_user("Guest")
		with self.assertRaises(frappe.AuthenticationError):
			self.listing()

	def finance_party(self):
		if not hasattr(self,'finance_supplier'):
			self.finance_supplier=frappe.get_doc({'doctype':'Supplier','supplier_name':self.marker+' supplier','supplier_type':'Company',
				'supplier_group':frappe.db.get_value('Supplier',{},'supplier_group')}).insert()
			self.supplier=self.finance_supplier.name
			for doc in (self.first,self.second):doc.supplier=self.supplier;doc.save()
		return frappe.get_doc('Company',self.company)

	def invoice(self,import_file=None,amount=100,advance=None,currency='SAR',exchange_rate=1):
		from frappe.utils import nowdate
		co=self.finance_party()
		from erpnext.accounts.party import get_party_account
		item=self.marker+' service'
		if not frappe.db.exists('Item',item):
			frappe.get_doc({'doctype':'Item','item_code':item,'item_name':item,'item_group':'All Item Groups','stock_uom':'Nos','is_stock_item':0}).insert()
		doc=frappe.new_doc('Purchase Invoice')
		doc.update({'company':self.company,'supplier':self.supplier,'currency':currency,'conversion_rate':exchange_rate,'credit_to':get_party_account('Supplier',self.supplier,self.company),
			'posting_date':nowdate(),'bill_no':uuid4().hex,'custom_vehicle_import_file':(import_file or self.first).name})
		doc.append('items',{'item_code':item,'qty':5,'rate':amount/5,'expense_account':co.default_expense_account,'cost_center':co.cost_center})
		doc.insert()
		if advance:
			doc.set_advances()
			doc.set('advances',[row for row in doc.advances if row.reference_name==advance])
			self.assertTrue(doc.advances)
			doc.save()
		doc.submit()
		return doc

	def payment(self,amount,references=None):
		from an_truck import financial_vouchers as payments
		from frappe.utils import nowdate
		co=self.finance_party()
		result=payments.save({'company':self.company,'payment_type':'Pay','party_type':'Supplier','party':self.supplier,
			'posting_date':nowdate(),'amount':amount,'account':co.default_cash_account,'mode_of_payment':'Cash',
			'references':references or []},request_key=uuid4().hex)
		payments.act(result['document']['name'],'submit')
		return result['document']['name']

	def metric(self,file=None):
		return next(row for row in self.listing()['rows'] if row.name==(file or self.first).name)

	def test_real_allocations_shared_payment_returns_and_cancellations(self):
		self.finance_party()
		self.order('first',self.first,currency='SAR',amount=100)
		self.order('second',self.second,currency='SAR',amount=100)
		first,second=self.invoice(),self.invoice(self.second)
		payment=self.payment(70,[{'reference_doctype':'Purchase Invoice','reference_name':first.name,'allocated_amount':50},
			{'reference_doctype':'Purchase Invoice','reference_name':second.name,'allocated_amount':20}])
		self.assertEqual(self.metric().paid_amount[0]['amount'],50)
		self.assertEqual(self.metric(self.second).paid_amount[0]['amount'],20)
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],50)
		from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note
		credit=make_debit_note(first.name)
		credit.items[0].qty=-1
		credit.insert();credit.submit()
		self.assertEqual(self.metric().paid_amount[0]['amount'],50)
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],30)
		credit.cancel()
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],50)
		from an_truck import financial_vouchers as payments
		payments.act(payment,'cancel')
		self.assertEqual(self.metric().paid_amount[0]['amount'],0)
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],100)

	def test_advance_is_counted_only_after_invoice_allocation(self):
		self.finance_party()
		self.order('advance',self.first,currency='SAR',amount=100)
		advance=self.payment(30)
		self.assertEqual(self.metric().paid_amount[0]['amount'],0)
		self.invoice(advance=advance)
		self.assertEqual(self.metric().paid_amount[0]['amount'],30)
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],70)

	def test_legacy_invoice_item_links_and_ambiguous_shared_invoice(self):
		self.finance_party()
		first=self.order('legacy invoice A',self.first,currency='SAR',amount=100)
		second=self.order('legacy invoice B',self.second,currency='SAR',amount=100)
		invoice=self.invoice()
		self.payment(30,[{'reference_doctype':'Purchase Invoice','reference_name':invoice.name,'allocated_amount':30}])
		# Emulate pre-existing item-only links on these new rollback-only fixtures.
		frappe.db.set_value('Purchase Invoice',invoice.name,'custom_vehicle_import_file',None)
		frappe.db.set_value('Purchase Invoice Item',invoice.items[0].name,'purchase_order',first.name)
		self.assertEqual(self.metric().paid_amount[0]['amount'],30)
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],70)
		self.assertEqual(self.metric(self.second).paid_amount[0]['amount'],0)
		frappe.get_doc({'doctype':'Purchase Invoice Item','parent':invoice.name,'parenttype':'Purchase Invoice',
			'parentfield':'items','idx':2,'purchase_order':second.name,'item_code':invoice.items[0].item_code}).db_insert()
		for page in (1,2):
			row=self.listing(page=page,page_length=1)['rows'][0]
			self.assertEqual(row.purchase_value[0]['amount'],100)
			self.assertIsNone(row.paid_amount)
			self.assertIsNone(row.outstanding_amount)

	def test_foreign_invoice_uses_recorded_base_amounts(self):
		from frappe.utils import nowdate
		co=self.finance_party()
		account=frappe.get_doc({'doctype':'Account','account_name':self.marker+' USD payable','company':self.company,
			'parent_account':frappe.db.get_value('Account',co.default_payable_account,'parent_account'),'account_type':'Payable','account_currency':'USD'}).insert()
		self.finance_supplier.default_currency='USD'
		self.finance_supplier.append('accounts',{'company':self.company,'account':account.name});self.finance_supplier.save()
		rate=frappe.db.get_value('Currency Exchange',{'date':nowdate(),'from_currency':'USD','to_currency':'SAR'},'exchange_rate')
		if not rate:
			rate=3.75
			frappe.get_doc({'doctype':'Currency Exchange','date':nowdate(),'from_currency':'USD','to_currency':'SAR','exchange_rate':rate,'for_buying':1,'for_selling':1}).insert()
		self.first.supplier_currency='USD';self.first.transaction_exchange_rate=rate;self.first.save()
		order=self.order('USD',self.first,currency='USD',amount=100)
		frappe.db.set_value('Purchase Order',order.name,'base_grand_total',100*rate)
		invoice=self.invoice(currency='USD',exchange_rate=rate)
		self.payment(75,[{'reference_doctype':'Purchase Invoice','reference_name':invoice.name,'allocated_amount':75/rate}])
		row=self.metric()
		self.assertEqual(row.purchase_value,[{'currency':'SAR','amount':100*rate}])
		self.assertEqual(row.paid_amount,[{'currency':'SAR','amount':75.0}])
		self.assertAlmostEqual(row.outstanding_amount[0]['amount'],100*rate-75,places=2)

	def test_cash_journal_and_non_cash_adjustment_are_distinct(self):
		from frappe.utils import nowdate
		co=self.finance_party();self.order('JE',self.first,currency='SAR',amount=100)
		invoice=self.invoice()
		for amount,account in [(20,co.default_cash_account),(10,co.default_expense_account)]:
			journal=frappe.new_doc('Journal Entry')
			journal.company=self.company;journal.posting_date=nowdate()
			journal.append('accounts',{'account':co.default_payable_account,'party_type':'Supplier','party':self.supplier,
				'reference_type':'Purchase Invoice','reference_name':invoice.name,'debit_in_account_currency':amount})
			journal.append('accounts',{'account':account,'credit_in_account_currency':amount,'cost_center':co.cost_center})
			journal.insert();journal.submit()
		self.assertEqual(self.metric().paid_amount[0]['amount'],20)
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],70)

	def test_late_payment_reconciliation_updates_the_same_invoice_allocation(self):
		co=self.finance_party()
		self.order('reconcile',self.first,currency='SAR',amount=100)
		invoice=self.invoice()
		payment=self.payment(30)
		self.assertEqual(self.metric().paid_amount[0]['amount'],0)
		rec=frappe.new_doc('Payment Reconciliation')
		rec.update({'company':self.company,'party_type':'Supplier','party':self.supplier,'receivable_payable_account':co.default_payable_account})
		rec.get_unreconciled_entries()
		inv=[r.as_dict() for r in rec.invoices if r.invoice_number==invoice.name]
		pay=[r.as_dict() for r in rec.payments if r.reference_name==payment]
		self.assertTrue(inv and pay)
		rec.allocate_entries({'invoices':inv,'payments':pay})
		rec.reconcile()
		self.assertEqual(self.metric().paid_amount[0]['amount'],30)
		self.assertEqual(self.metric().outstanding_amount[0]['amount'],70)

	def workbook(self,values):
		import base64
		from frappe.utils.xlsxutils import make_xlsx
		from an_truck_portal.api.import_file_excel import FIELDS
		return base64.b64encode(make_xlsx([list(FIELDS.values()),*values],'Import').getvalue()).decode()

	def test_excel_preview_atomic_validation_duplicates_and_create(self):
		from an_truck_portal.api import import_file_excel as excel
		name='00-'+self.marker+' إنشاء'
		content=self.workbook([[name,self.supplier,'China','SAR',2,1,'ملاحظة'],[self.first.name,self.supplier,'China','SAR',1,1,'']])
		preview=excel.import_rows(self.company,content)
		self.assertTrue(preview['can_import']);self.assertFalse(frappe.db.exists('Vehicle Import File',name))
		self.assertEqual([row['status'] for row in preview['rows']],['valid','skipped'])
		invalid=self.workbook([[name,self.supplier,'China','SAR',2,1,''],[self.marker+' bad','NO-SUPPLIER','China','SAR',1,1,'']])
		result=excel.import_rows(self.company,invalid,operation='import')
		self.assertFalse(result['can_import']);self.assertFalse(frappe.db.exists('Vehicle Import File',name))
		result=excel.import_rows(self.company,content,operation='import')
		self.assertEqual(result['created'],1)
		self.assertEqual(frappe.get_doc('Vehicle Import File',name).notes,'ملاحظة')
		self.assertEqual(excel.import_rows(self.company,content,operation='import')['created'],0)
		self.assertFalse(excel.import_rows(self.company,content,duplicates='error')['can_import'])
		formula=self.workbook([['=1+1',self.supplier,'China','SAR',1,1,'']])
		# Standard XLSX writer stores formula-like input literally, never executes it.
		self.assertTrue(excel.import_rows(self.company,formula)['can_import'])
		from openpyxl import Workbook
		from io import BytesIO
		import base64
		book=Workbook();sheet=book.active
		from an_truck_portal.api.import_file_excel import FIELDS
		sheet.append(list(FIELDS.values()));sheet.append(['=1+1',self.supplier,'China','SAR',1,1,''])
		stream=BytesIO();book.save(stream);book.close()
		self.assertFalse(excel.import_rows(self.company,base64.b64encode(stream.getvalue()).decode())['can_import'])
		# A late native save failure must roll back earlier rows in the same batch.
		from frappe.model.document import Document
		original_insert=Document.insert
		first,second=self.marker+' atomic A',self.marker+' atomic B'
		def reject_second(doc,*args,**kwargs):
			if doc.doctype=='Vehicle Import File' and doc.import_title==second:
				frappe.throw('Test native validation failure')
			return original_insert(doc,*args,**kwargs)
		with patch.object(Document,'insert',new=reject_second):
			result=excel.import_rows(self.company,self.workbook([[n,self.supplier,'China','SAR',1,1,''] for n in (first,second)]),operation='import')
		self.assertEqual(result['created'],0)
		self.assertFalse(frappe.db.exists('Vehicle Import File',first))
		self.assertFalse(frappe.db.exists('Vehicle Import File',second))

	def test_excel_permissions_company_boundaries_and_template(self):
		from an_truck_portal.api import import_file_excel as excel
		user=frappe.get_doc({'doctype':'User','email':uuid4().hex+'@example.test','first_name':'Excel viewer','send_welcome_email':0,
			'roles':[{'role':'AN Truck Portal User'},{'role':'AN Truck Viewer'}]}).insert()
		content=self.workbook([[self.marker+' denied',self.supplier,'China','SAR',1,1,'']])
		frappe.set_user(user.name)
		with self.assertRaises(frappe.PermissionError):excel.import_rows(self.company,content,operation='import')
		with self.assertRaises(frappe.PermissionError):excel.export(company=self.company)
		frappe.set_user('Administrator')
		user.append('roles',{'role':'AN Truck Manager'});user.append('roles',{'role':'Accounts User'});user.save()
		frappe.get_doc({'doctype':'User Permission','user':user.name,'allow':'Company','for_value':self.company,'apply_to_all_doctypes':1}).insert()
		frappe.set_user(user.name)
		other=frappe.db.get_value('Company',{'name':['!=',self.company]},'name')
		with self.assertRaises(frappe.PermissionError):excel.import_rows(other,content,operation='import')
		frappe.set_user('Administrator');excel.template(self.company)
		self.assertTrue(frappe.local.response.filecontent.startswith(b'PK'))

	def test_excel_export_exact_headers_order_filter_and_unicode(self):
		from an_truck_portal.api import import_file_excel as excel
		from an_truck_portal.import_file_metrics import COLUMNS
		from openpyxl import load_workbook
		from io import BytesIO
		from frappe.translate import print_language
		for lang in ('ar','en'):
			with print_language(lang):
				excel.export(company=self.company,search=self.marker)
				book=load_workbook(BytesIO(frappe.local.response.filecontent),data_only=False)
				data=list(book.active.values)
				self.assertEqual(list(data[0]),[excel._label(label) for label in COLUMNS.values()])
				self.assertEqual(len(data),3)
				self.assertEqual(len(data[0]),11)
				self.assertEqual(book.active.sheet_view.rightToLeft,True if lang=='ar' else None)
				book.close()
