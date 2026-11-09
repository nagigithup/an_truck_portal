"""Native receipt/LCV tests: new fixtures only, every posting rolled back."""
import hashlib
from uuid import uuid4
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from an_truck_portal import single_truck_cost as api
from an_truck_portal.api import import_file as endpoints


class TestSingleTruckCost(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.user=frappe.session.user
		frappe.set_user('Administrator')
		frappe.db.savepoint('single_cost_test')
		self.before=self.fingerprint()
		self.mark='Single truck '+uuid4().hex[:10]
		self.company=frappe.defaults.get_global_default('company')
		self.co=frappe.get_doc('Company',self.company)
		self.supplier=frappe.db.get_value('Supplier',{'disabled':0},'name')
		self.warehouse=frappe.db.get_value('Warehouse',{'company':self.company,'disabled':0,'is_group':0},'name')
		self.account=self.co.default_expense_account
		self.file=frappe.get_doc({'doctype':'Vehicle Import File','import_title':self.mark,'company':self.company,
			'supplier':self.supplier,'supplier_currency':self.co.default_currency,'total_expected_vehicles':10,'transaction_exchange_rate':1}).insert()
		self.item=frappe.get_doc({'doctype':'Item','item_code':self.mark,'item_name':self.mark,
			'item_group':frappe.get_single('AN Truck Settings').vehicle_item_group,'stock_uom':'Nos','is_stock_item':1,'has_serial_no':1}).insert()

	def tearDown(self):
		frappe.set_user('Administrator')
		frappe.db.rollback(save_point='single_cost_test')
		self.assertEqual(self.before,self.fingerprint(),'Existing vehicle/stock/accounting records changed')
		frappe.set_user(self.user)
		super().tearDown()

	def fingerprint(self):
		rows={dt:frappe.get_all(dt,fields=['name','modified','docstatus'],order_by='name') for dt in (
			'Vehicle Master','Vehicle Import File','Purchase Receipt','Purchase Receipt Item','Serial No',
			'Landed Cost Voucher','Stock Reconciliation','Stock Reconciliation Item','Serial and Batch Bundle',
			'Serial and Batch Entry','GL Entry','Stock Ledger Entry','Bin')}
		return hashlib.sha256(frappe.as_json(rows).encode()).hexdigest()

	def receipt(self,quantities=(1,1)):
		pr=frappe.new_doc('Purchase Receipt')
		pr.update({'company':self.company,'supplier':self.supplier,'currency':self.co.default_currency,
			'custom_vehicle_import_file':self.file.name})
		vins=[]
		for index,qty in enumerate(quantities):
			serials=[self.mark+' VIN '+uuid4().hex[:5] for _ in range(qty)]
			vins.extend(serials)
			pr.append('items',{'item_code':self.item.name,'qty':qty,'rate':1000,'warehouse':self.warehouse,
				'cost_center':self.co.cost_center,'serial_no':'\n'.join(serials),'use_serial_batch_fields':1})
		pr.insert();pr.submit()
		self.file.reload()
		return pr,[frappe.get_doc('Vehicle Master',vin) for vin in vins]

	def data(self,vehicle,amount=100):
		return {'vehicle':vehicle.name,'amount':amount,'expense_account':self.account,'description':'تكلفة مباشرة'}

	def create(self,data,key=None):
		preview=endpoints.preview_single_truck_cost(self.file.name,data)
		return endpoints.create_single_truck_cost(self.file.name,data,key or uuid4().hex,preview['confirmation'])

	def test_native_manual_allocation_only_one_vin_and_history(self):
		pr,vehicles=self.receipt()
		first,other=vehicles
		before_other=frappe.get_doc('Vehicle Master',other.name).as_dict()
		summary=endpoints.preview_single_truck_cost(self.file.name,self.data(first))['summary']
		self.assertEqual((summary['vin'],summary['purchase_receipt'],summary['warehouse'],summary['currency']),
			(first.vin,pr.name,self.warehouse,self.co.default_currency))
		self.assertFalse(frappe.db.exists('Landed Cost Voucher',{'custom_vehicle_import_file':self.file.name}))
		result=self.create(self.data(first))
		voucher=frappe.get_doc('Landed Cost Voucher',result['name'])
		self.assertEqual(voucher.docstatus,1)
		self.assertEqual(len(voucher.items),1)
		self.assertEqual(voucher.items[0].purchase_receipt_item,pr.items[0].name)
		self.assertEqual(voucher.items[0].applicable_charges,100)
		self.assertEqual(voucher.get(api.VEHICLE),first.name)
		pr.reload()
		self.assertEqual([row.landed_cost_voucher_amount for row in pr.items],[100,0])
		self.assertEqual([frappe.db.get_value('Serial No',v.vin,'purchase_rate') for v in vehicles],[1100,1000])
		self.assertEqual(frappe.get_doc('Vehicle Master',other.name).as_dict(),before_other)
		from an_truck.transactions import get_import_workspace
		history=get_import_workspace(self.file.name)['costs']['rows']
		self.assertTrue(any(row['voucher']==voucher.name and first.vin in row['description'] for row in history))
		# Targeted native cancellation resets only this new vehicle's cost.
		voucher.cancel();pr.reload()
		self.assertEqual([row.landed_cost_voucher_amount for row in pr.items],[0,0])
		self.assertEqual(frappe.get_doc('Vehicle Master',other.name).as_dict(),before_other)

	def test_shared_row_routes_to_revaluation_and_forged_lcv_is_blocked(self):
		pr,vehicles=self.receipt((2,))
		target=endpoints.get_single_truck_cost_target(self.file.name,vehicles[0].name)
		self.assertTrue(target['eligible'])
		self.assertEqual(target['doctype'],'Stock Reconciliation')
		self.assertEqual(endpoints.preview_single_truck_cost(self.file.name,self.data(vehicles[0]))['summary']['doctype'],'Stock Reconciliation')
		with self.assertRaises(frappe.ValidationError):endpoints.create_single_truck_cost(self.file.name,self.data(vehicles[0]),uuid4().hex,'forged')
		self.assertFalse(frappe.db.exists('Landed Cost Voucher',{'custom_vehicle_import_file':self.file.name}))
		# Native Desk insert with a manually edited qty=1 cannot bypass the guard.
		doc=frappe.new_doc('Landed Cost Voucher')
		doc.update({'company':self.company,'custom_vehicle_import_file':self.file.name,api.VEHICLE:vehicles[0].name,'distribute_charges_based_on':'Distribute Manually'})
		doc.append('purchase_receipts',{'receipt_document_type':'Purchase Receipt','receipt_document':pr.name})
		doc.get_items_from_purchase_receipts();doc.items[0].qty=1;doc.items[0].applicable_charges=100
		doc.append('taxes',{'expense_account':self.account,'amount':100,'description':'unsafe'})
		with self.assertRaises(frappe.ValidationError):doc.insert()

	def test_persistent_retry_dedup_and_distinct_additional_costs(self):
		pr,vehicles=self.receipt((1,))
		data=self.data(vehicles[0]);preview=endpoints.preview_single_truck_cost(self.file.name,data)
		key=uuid4().hex
		first=endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		second=endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		self.assertEqual(first['name'],second['name'])
		self.assertEqual(frappe.db.count('Landed Cost Voucher',{'custom_vehicle_import_file':self.file.name}),1)
		with self.assertRaises(frappe.ValidationError):endpoints.create_single_truck_cost(self.file.name,{**data,'amount':200},key,preview['confirmation'])
		self.create(data)
		pr.reload();self.assertEqual(pr.items[0].landed_cost_voucher_amount,200)
		self.assertEqual(frappe.db.count('Landed Cost Voucher',{'custom_vehicle_import_file':self.file.name}),2)

	def test_bulk_workflow_remains_native_and_updates_all_rows(self):
		pr,vehicles=self.receipt()
		result=endpoints.create_landed_cost_voucher(self.file.name,{'purchase_receipts':[{'receipt_document':pr.name}],
			'allocation_basis':'Qty','taxes':[{'expense_account':self.account,'description':'bulk','amount':100,'currency':self.co.default_currency,'exchange_rate':1}]},1,uuid4().hex)
		doc=frappe.get_doc('Landed Cost Voucher',result['name'])
		self.assertFalse(doc.get(api.VEHICLE))
		self.assertEqual([row.applicable_charges for row in doc.items],[50,50])
		pr.reload();self.assertEqual([row.landed_cost_voucher_amount for row in pr.items],[50,50])

	def test_failed_native_submission_rolls_back_cost_and_can_retry(self):
		pr,vehicles=self.receipt((1,))
		serial_rate=frappe.db.get_value('Serial No',vehicles[0].vin,'purchase_rate')
		data=self.data(vehicles[0]);preview=endpoints.preview_single_truck_cost(self.file.name,data)
		key=uuid4().hex
		from erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher import LandedCostVoucher
		original=LandedCostVoucher.on_submit
		def fail_after_valuation(doc):
			original(doc)
			frappe.throw('Test failure after native valuation')
		with patch.object(LandedCostVoucher,'on_submit',new=fail_after_valuation):
			with self.assertRaises(frappe.ValidationError):endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		self.assertFalse(frappe.db.exists('Landed Cost Voucher',{'custom_vehicle_import_file':self.file.name}))
		pr.reload();self.assertEqual(pr.items[0].landed_cost_voucher_amount,0)
		self.assertEqual(frappe.db.get_value('Serial No',vehicles[0].vin,'purchase_rate'),serial_rate)
		result=endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		self.assertEqual(result['docstatus'],1)

	def test_scope_search_tampering_and_native_currency_conversion(self):
		pr,vehicles=self.receipt((1,))
		vehicle=vehicles[0];data=self.data(vehicle)
		self.assertEqual([row['value'] for row in endpoints.search_single_truck_cost_vehicles(self.file.name,vehicle.vin)],[vehicle.name])
		other=frappe.get_doc({'doctype':'Vehicle Import File','import_title':self.mark+' other','company':self.company,
			'supplier':self.supplier,'supplier_currency':self.co.default_currency,'transaction_exchange_rate':1}).insert()
		self.assertEqual(endpoints.search_single_truck_cost_vehicles(other.name,vehicle.vin),[])
		with self.assertRaises(frappe.PermissionError):endpoints.get_single_truck_cost_target(other.name,vehicle.name)
		preview=endpoints.preview_single_truck_cost(self.file.name,data)
		with self.assertRaises(frappe.ValidationError):endpoints.create_single_truck_cost(self.file.name,{**data,'amount':101},uuid4().hex,preview['confirmation'])
		foreign_account=frappe.get_doc({'doctype':'Account','account_name':self.mark+' USD cost','company':self.company,
			'parent_account':frappe.db.get_value('Account',self.account,'parent_account'),'account_currency':'USD'}).insert()
		from frappe.utils import nowdate
		rate=frappe.db.get_value('Currency Exchange',{'date':nowdate(),'from_currency':'USD','to_currency':self.co.default_currency},'exchange_rate')
		if not rate:
			rate=4.13
			frappe.get_doc({'doctype':'Currency Exchange','date':nowdate(),'from_currency':'USD','to_currency':self.co.default_currency,
				'exchange_rate':rate,'for_buying':1,'for_selling':1}).insert()
		converted=endpoints.preview_single_truck_cost(self.file.name,{**data,'expense_account':foreign_account.name})['summary']
		self.assertEqual(converted['currency'],'USD')
		self.assertAlmostEqual(converted['company_amount'],100*converted['exchange_rate'],places=2)
		self.assertNotEqual(converted['exchange_rate'],1)
		result=self.create(data)
		doc=frappe.get_doc('Landed Cost Voucher',result['name'])
		# The same safety invariant remains active on later Desk/API validations.
		doc.set(api.VEHICLE,None)
		with self.assertRaises(frappe.ValidationError):doc.run_method('validate')

	def test_scope_permissions_invalid_amount_and_confirmation(self):
		_,vehicles=self.receipt((1,))
		data=self.data(vehicles[0])
		with self.assertRaises(frappe.ValidationError):endpoints.preview_single_truck_cost(self.file.name,{**data,'amount':'NaN'})
		with self.assertRaises(frappe.ValidationError):endpoints.preview_single_truck_cost(self.file.name,{**data,'amount':'1e999'})
		with self.assertRaises(frappe.ValidationError):endpoints.preview_single_truck_cost(self.file.name,{**data,'amount':-1})
		with self.assertRaises(frappe.ValidationError):endpoints.create_single_truck_cost(self.file.name,data,uuid4().hex,'wrong')
		user=frappe.get_doc({'doctype':'User','email':uuid4().hex+'@example.test','first_name':'Cost viewer',
			'send_welcome_email':0,'roles':[{'role':'AN Truck Portal User'},{'role':'AN Truck Viewer'}]}).insert()
		frappe.set_user(user.name)
		with self.assertRaises(frappe.PermissionError):endpoints.get_single_truck_cost_target(self.file.name,vehicles[0].name)
		frappe.set_user('Administrator')
		self.file.status='Completed';self.file.save()
		with self.assertRaises(frappe.PermissionError):self.create(data)

	def test_normal_stock_user_can_submit_only_in_permitted_company(self):
		_,vehicles=self.receipt((1,2))
		other_company=frappe.db.get_value('Company',{'name':['!=',self.company]},'name')
		foreign=frappe.get_doc({'doctype':'Vehicle Import File','import_title':self.mark+' foreign',
			'company':other_company,'supplier':self.supplier,'supplier_currency':self.co.default_currency,'transaction_exchange_rate':1}).insert()
		user=frappe.get_doc({'doctype':'User','email':uuid4().hex+'@example.test','first_name':'Truck cost operator','send_welcome_email':0,
			'roles':[{'role':r} for r in ('AN Truck Portal User','AN Truck Viewer','Stock Manager','Purchase Manager','Accounts User')]}).insert()
		frappe.get_doc({'doctype':'User Permission','user':user.name,'allow':'Company','for_value':self.company,'apply_to_all_doctypes':1}).insert()
		frappe.set_user(user.name)
		self.assertTrue(frappe.has_permission('Landed Cost Voucher','submit'))
		# Installed controller hooks may restrict Company read independently of
		# stock roles. Preserve that denial; a native explicit read share is a
		# legitimate existing grant, created only for this rollback-only test user.
		if not frappe.has_permission('Company','read',doc=self.co):
			with self.assertRaises(frappe.PermissionError):endpoints.get_single_truck_cost_target(self.file.name,vehicles[0].name)
			frappe.set_user('Administrator')
			frappe.share.add('Company',self.company,user.name,read=1,write=0,share=0,notify=0)
			frappe.set_user(user.name)
		with self.assertRaises(frappe.PermissionError):endpoints.get_single_truck_cost_target(foreign.name,vehicles[0].name)
		for vehicle,doctype in zip(vehicles,('Landed Cost Voucher','Stock Reconciliation')):
			result=self.create(self.data(vehicle))
			self.assertEqual((result['docstatus'],result['doctype']),(1,doctype))

	def serial_rates(self, vehicles):
		from erpnext.stock.utils import get_incoming_rate
		from frappe.utils import nowdate,nowtime
		return [get_incoming_rate({'item_code':self.item.name,'warehouse':self.warehouse,
			'posting_date':nowdate(),'posting_time':nowtime(),'serial_no':v.vin,'qty':-1,'company':self.company}) for v in vehicles]

	def test_audit_native_manual_lcv_5000_is_shared_across_ten_vins(self):
		"""Manual is per PR item: SAR 5,000 / qty 10 = SAR 500 per VIN."""
		self.assertEqual(self.co.default_currency,'SAR')
		pr,vehicles=self.receipt((10,))
		self.assertEqual(self.serial_rates(vehicles),[1000]*10)
		self.assertEqual(endpoints.preview_single_truck_cost(self.file.name,self.data(vehicles[0],5000))['summary']['doctype'],'Stock Reconciliation')
		# Audit the unmodified native path, without pretending it is a targeted LCV.
		doc=frappe.new_doc('Landed Cost Voucher')
		doc.update({'company':self.company,'custom_vehicle_import_file':self.file.name,
			'distribute_charges_based_on':'Distribute Manually'})
		doc.append('purchase_receipts',{'receipt_document_type':'Purchase Receipt','receipt_document':pr.name})
		doc.get_items_from_purchase_receipts()
		doc.items[0].applicable_charges=5000
		doc.append('taxes',{'expense_account':self.account,'amount':5000,'description':'Native per-row allocation audit'})
		doc.insert();doc.submit();pr.reload()
		self.assertEqual(pr.items[0].landed_cost_voucher_amount,5000)
		self.assertEqual(pr.items[0].valuation_rate,1500)
		self.assertEqual(self.serial_rates(vehicles),[1500]*10)
		for vehicle in vehicles:
			vehicle.reload()
			self.assertEqual((vehicle.landed_cost_added,vehicle.final_valuation_rate),(500,1500))
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'actual_qty'),10)
		gl=frappe.get_all('GL Entry',filters={'voucher_type':'Purchase Receipt','voucher_no':pr.name,'is_cancelled':0},fields=['account','debit','credit'])
		# LCV-native postings are against the receipt; its inventory GL must rise
		# by the row's entire 5,000, not just one VIN's cost in a custom ledger.
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'stock_value'),15000)
		self.assertEqual((sum(r.debit for r in gl),sum(r.credit for r in gl)),(15000,15000))
		self.assertEqual(sum(r.credit-r.debit for r in gl if r.account==self.account),5000)

	def test_audit_native_selected_serial_reconciliation_preserves_other_nine(self):
		"""A different native document can revalue an on-hand VIN; VM stays PR-based."""
		from erpnext.stock.serial_batch_bundle import SerialBatchCreation
		from frappe.utils import nowdate,nowtime
		pr,vehicles=self.receipt((10,))
		pr_before=frappe.get_doc('Purchase Receipt',pr.name).as_dict()
		others_before=[v.as_dict() for v in vehicles[1:]]
		bundle=SerialBatchCreation({'item_code':self.item.name,'warehouse':self.warehouse,'voucher_type':'Stock Reconciliation',
			'company':self.company,'qty':1,'avg_rate':6000,'serial_nos':[vehicles[0].vin],
			'posting_date':nowdate(),'posting_time':nowtime(),'type_of_transaction':'Inward','do_not_submit':True}).make_serial_and_batch_bundle()
		reco=frappe.new_doc('Stock Reconciliation')
		reco.update({'purpose':'Stock Reconciliation','company':self.company,'posting_date':nowdate(),
			'posting_time':nowtime(),'set_posting_time':1,'expense_account':self.co.stock_adjustment_account,'cost_center':self.co.cost_center})
		reco.append('items',{'item_code':self.item.name,'warehouse':self.warehouse,'qty':1,'valuation_rate':6000,
			'reconcile_all_serial_batch':0,'serial_and_batch_bundle':bundle.name,'use_serial_batch_fields':0})
		reco.insert();reco.submit()
		self.assertEqual(reco.difference_amount,5000)
		self.assertEqual((reco.items[0].current_qty,reco.items[0].qty),(1,1))
		self.assertEqual(self.serial_rates(vehicles),[6000]+[1000]*9)
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'actual_qty'),10)
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'stock_value'),15000)
		entries=frappe.get_all('Stock Ledger Entry',filters={'voucher_type':reco.doctype,'voucher_no':reco.name,'is_cancelled':0},fields=['actual_qty','stock_value_difference'])
		self.assertEqual(sorted(r.actual_qty for r in entries),[-1,1])
		self.assertEqual(sum(r.stock_value_difference for r in entries),5000)
		gl=frappe.get_all('GL Entry',filters={'voucher_type':reco.doctype,'voucher_no':reco.name,'is_cancelled':0},fields=['account','debit','credit'])
		self.assertEqual((sum(r.debit for r in gl),sum(r.credit for r in gl)),(5000,5000))
		self.assertEqual(frappe.get_doc('Purchase Receipt',pr.name).as_dict(),pr_before)
		self.assertEqual([frappe.get_doc('Vehicle Master',v.name).as_dict() for v in vehicles[1:]],others_before)
		vehicles[0].reload()
		self.assertEqual(vehicles[0].final_valuation_rate,1000,'Existing VM source is still the PR, not serial revaluations')

	def test_audit_sold_vin_in_shared_row_stays_out_of_stock_and_unmodified(self):
		from frappe.utils import now
		from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import get_available_serial_nos
		pr,vehicles=self.receipt((10,))
		customer=frappe.get_doc({'doctype':'Customer','customer_name':self.mark+' buyer','customer_type':'Individual',
			'customer_group':frappe.db.get_value('Customer Group',{'is_group':0},'name'),
			'territory':frappe.db.get_value('Territory',{'is_group':0},'name')}).insert()
		invoice=frappe.new_doc('Sales Invoice')
		invoice.update({'company':self.company,'customer':customer.name,'currency':self.co.default_currency,'update_stock':1,
			'custom_vehicle_import_file':self.file.name})
		invoice.append('items',{'item_code':self.item.name,'qty':1,'rate':2000,'warehouse':self.warehouse,
			'income_account':self.co.default_income_account,'expense_account':self.account,'cost_center':self.co.cost_center,
			'custom_vehicle_master':vehicles[0].name,'custom_vin':vehicles[0].vin,'serial_no':vehicles[0].vin,'use_serial_batch_fields':1})
		invoice.insert();invoice.submit()
		self.assertFalse(frappe.db.get_value('Serial No',vehicles[0].vin,'warehouse'))
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'actual_qty'),9)
		available=get_available_serial_nos(frappe._dict(item_code=self.item.name,warehouse=self.warehouse,posting_datetime=now()))
		self.assertNotIn(vehicles[0].vin,{r.serial_no for r in available})
		self.assertEqual(len(available),9)
		stock_value=frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'stock_value')
		cogs=sum(r.debit-r.credit for r in frappe.get_all('GL Entry',filters={'voucher_type':invoice.doctype,'voucher_no':invoice.name,
			'is_cancelled':0,'account':self.account},fields=['debit','credit']))
		self.assertEqual((stock_value,cogs),(9000,1000))
		with self.assertRaises(frappe.ValidationError):self.create(self.data(vehicles[0],5000))
		self.assertFalse(frappe.db.exists('Landed Cost Voucher',{'custom_vehicle_import_file':self.file.name}))
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'stock_value'),9000)
		for vehicle in vehicles:
			vehicle.reload();self.assertEqual(vehicle.final_valuation_rate,1000)

	def test_ten_trucks_5000_revaluation_integrates_cost_history_retry_and_cancel(self):
		pr,vehicles=self.receipt((10,))
		pr_before=frappe.get_doc('Purchase Receipt',pr.name).as_dict();others=[v.as_dict() for v in vehicles[1:]]
		data=self.data(vehicles[0],5000)
		bundles=frappe.db.count('Serial and Batch Bundle')
		preview=endpoints.preview_single_truck_cost(self.file.name,data)
		self.assertEqual(frappe.db.count('Serial and Batch Bundle'),bundles,'Preview must not save any serial bundles')
		self.assertEqual(preview['summary']['doctype'],'Stock Reconciliation')
		self.assertEqual((preview['summary']['current_valuation'],preview['summary']['new_valuation']),(1000,6000))
		key=uuid4().hex
		result=endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		self.assertEqual(result['doctype'],'Stock Reconciliation')
		doc=frappe.get_doc(result['doctype'],result['name'])
		self.assertEqual((doc.items[0].qty,doc.items[0].current_qty,doc.difference_amount),(1,1,5000))
		self.assertEqual(self.serial_rates(vehicles),[6000]+[1000]*9)
		vehicles[0].reload()
		self.assertEqual((vehicles[0].final_valuation_rate,vehicles[0].custom_portal_serial_cost_adjustment),(6000,5000))
		self.assertEqual(frappe.get_doc('Purchase Receipt',pr.name).as_dict(),pr_before)
		self.assertEqual([frappe.get_doc('Vehicle Master',v.name).as_dict() for v in vehicles[1:]],others)
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'actual_qty'),10)
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'stock_value'),15000)
		from an_truck.transactions import get_import_workspace
		gl=frappe.get_all('GL Entry',filters={'voucher_type':doc.doctype,'voucher_no':doc.name,'is_cancelled':0},fields=['debit','credit'])
		self.assertEqual((sum(r.debit for r in gl),sum(r.credit for r in gl)),(5000,5000))
		stock=frappe.get_all('Stock Ledger Entry',filters={'voucher_type':doc.doctype,'voucher_no':doc.name,'is_cancelled':0},fields=['actual_qty','stock_value_difference'])
		self.assertEqual(sorted(r.actual_qty for r in stock),[-1,1])
		self.assertEqual(sum(r.stock_value_difference for r in stock),5000)
		from an_truck_portal.api.records import get_vehicle_form
		fields={f['fieldname']:f['value'] for section in get_vehicle_form(vehicles[0].name)['sections'] for f in section['fields']}
		self.assertEqual((fields['custom_portal_serial_cost_adjustment'],fields['final_valuation_rate']),(5000,6000))
		costs=get_import_workspace(self.file.name)['costs']
		self.assertTrue(any(r['voucher']==doc.name and r['doctype']=='Stock Reconciliation' for r in costs['rows']))
		self.assertEqual(costs['total'],5000)
		self.assertEqual(endpoints.get_single_truck_revaluation(doc.name)['amount'],5000)
		retry=endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		self.assertEqual(retry['name'],doc.name)
		self.assertEqual(frappe.db.count('Stock Reconciliation',{api.VEHICLE:vehicles[0].name}),1)
		doc.cancel();vehicles[0].reload()
		self.assertEqual(self.serial_rates(vehicles),[1000]*10)
		self.assertEqual((vehicles[0].final_valuation_rate,vehicles[0].custom_portal_serial_cost_adjustment),(1000,0))
		self.assertEqual(get_import_workspace(self.file.name)['costs']['total'],0)

	def test_revaluation_separate_cost_cancel_order_and_audit_links(self):
		_,vehicles=self.receipt((10,))
		first=self.create(self.data(vehicles[0],5000))
		second=self.create(self.data(vehicles[0],250))
		self.assertNotEqual(first['name'],second['name'])
		self.assertEqual(self.serial_rates(vehicles),[6250]+[1000]*9)
		self.assertEqual(frappe.db.get_value('Vehicle Master',vehicles[0].name,'final_valuation_rate'),6250)
		first=frappe.get_doc(first['doctype'],first['name'])
		second=frappe.get_doc(second['doctype'],second['name'])
		first.set(api.VEHICLE,None)
		with self.assertRaises(frappe.ValidationError):first.run_method('validate')
		first.reload()
		with self.assertRaises(frappe.ValidationError):first.cancel()
		first.reload();second.cancel();first.cancel()
		self.assertEqual(self.serial_rates(vehicles),[1000]*10)
		self.assertEqual(frappe.db.get_value('Vehicle Master',vehicles[0].name,'final_valuation_rate'),1000)

	def test_revaluation_failure_rolls_back_native_bundles_valuation_and_master(self):
		_,vehicles=self.receipt((10,))
		data=self.data(vehicles[0],5000);key=uuid4().hex
		preview=endpoints.preview_single_truck_cost(self.file.name,data)
		before=self.fingerprint()
		from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import StockReconciliation
		original=StockReconciliation.on_submit
		def fail_after_stock(doc):
			original(doc)
			frappe.throw('Test failure after native serial reconciliation')
		with patch.object(StockReconciliation,'on_submit',new=fail_after_stock):
			with self.assertRaises(frappe.ValidationError):endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		self.assertEqual(before,self.fingerprint())
		result=endpoints.create_single_truck_cost(self.file.name,data,key,preview['confirmation'])
		self.assertEqual(result['docstatus'],1)
		self.assertEqual(self.serial_rates(vehicles),[6000]+[1000]*9)

	def test_revaluation_disallows_pooled_serials_foreign_expense_and_restricted_user(self):
		_,vehicles=self.receipt((10,))
		foreign=frappe.get_doc({'doctype':'Account','account_name':self.mark+' foreign cost','company':self.company,
			'parent_account':frappe.db.get_value('Account',self.account,'parent_account'),'account_currency':'USD'}).insert()
		with self.assertRaises(frappe.ValidationError):endpoints.preview_single_truck_cost(self.file.name,
			{**self.data(vehicles[0]),'expense_account':foreign.name})
		user=frappe.get_doc({'doctype':'User','email':uuid4().hex+'@example.test','first_name':'Cost viewer',
			'send_welcome_email':0,'roles':[{'role':'AN Truck Portal User'},{'role':'AN Truck Viewer'}]}).insert()
		frappe.set_user(user.name)
		with self.assertRaises(frappe.PermissionError):endpoints.preview_single_truck_cost(self.file.name,self.data(vehicles[0]))
		frappe.set_user('Administrator')
		self.assertFalse(frappe.db.exists('Stock Reconciliation',{api.VEHICLE:vehicles[0].name}))
		self.item.use_serial_no_wise_valuation=0;self.item.save()
		target=endpoints.get_single_truck_cost_target(self.file.name,vehicles[0].name)
		self.assertFalse(target['eligible'])
		self.assertEqual(target['reason'],'Serial No Wise Valuation must be enabled for this item.')

	def test_revalued_vin_sale_uses_native_6000_cogs_and_blocks_further_revaluation(self):
		_,vehicles=self.receipt((10,))
		self.create(self.data(vehicles[0],5000))
		customer=frappe.get_doc({'doctype':'Customer','customer_name':self.mark+' buyer','customer_type':'Individual',
			'customer_group':frappe.db.get_value('Customer Group',{'is_group':0},'name'),
			'territory':frappe.db.get_value('Territory',{'is_group':0},'name')}).insert()
		invoice=frappe.new_doc('Sales Invoice')
		invoice.update({'company':self.company,'customer':customer.name,'currency':self.co.default_currency,'update_stock':1,
			'custom_vehicle_import_file':self.file.name})
		invoice.append('items',{'item_code':self.item.name,'qty':1,'rate':10000,'warehouse':self.warehouse,
			'income_account':self.co.default_income_account,'expense_account':self.account,'cost_center':self.co.cost_center,
			'custom_vehicle_master':vehicles[0].name,'custom_vin':vehicles[0].vin,'serial_no':vehicles[0].vin,'use_serial_batch_fields':1})
		invoice.insert();invoice.submit()
		cogs=sum(r.debit-r.credit for r in frappe.get_all('GL Entry',filters={'voucher_type':invoice.doctype,
			'voucher_no':invoice.name,'is_cancelled':0,'account':self.account},fields=['debit','credit']))
		self.assertEqual(cogs,6000)
		self.assertEqual(frappe.db.get_value('Bin',{'item_code':self.item.name,'warehouse':self.warehouse},'stock_value'),9000)
		self.assertEqual(frappe.db.get_value('Vehicle Master',vehicles[0].name,'final_valuation_rate'),6000)
		with self.assertRaises(frappe.ValidationError):self.create(self.data(vehicles[0],50))

	def test_bulk_lcv_repost_keeps_revaluation_master_and_gl_consistent(self):
		pr,vehicles=self.receipt((10,))
		result=self.create(self.data(vehicles[0],5000))
		# Native LCV raises the original receipt to 1,100 per VIN. The native
		# reconciliation is an absolute target of 6,000, so its posted delta
		# becomes 4,900. This must not be counted as another 5,000.
		endpoints.create_landed_cost_voucher(self.file.name,{'purchase_receipts':[{'receipt_document':pr.name}],
			'allocation_basis':'Qty','taxes':[{'expense_account':self.account,'description':'bulk after revaluation',
			'amount':1000,'currency':self.co.default_currency,'exchange_rate':1}]},1,uuid4().hex)
		doc=frappe.get_doc(result['doctype'],result['name'])
		self.assertEqual(doc.difference_amount,4900)
		self.assertEqual(self.serial_rates(vehicles),[6000]+[1100]*9)
		self.assertEqual(frappe.db.get_value('Vehicle Master',vehicles[0].name,'final_valuation_rate'),6000)
		gl=frappe.get_all('GL Entry',filters={'voucher_type':doc.doctype,'voucher_no':doc.name,'is_cancelled':0},fields=['debit','credit'])
		self.assertEqual((sum(r.debit for r in gl),sum(r.credit for r in gl)),(4900,4900))
