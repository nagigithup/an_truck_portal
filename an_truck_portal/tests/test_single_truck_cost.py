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
			'Landed Cost Voucher','GL Entry','Stock Ledger Entry','Bin')}
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

	def test_shared_row_blocked_in_preview_submission_and_desk(self):
		pr,vehicles=self.receipt((2,))
		target=endpoints.get_single_truck_cost_target(self.file.name,vehicles[0].name)
		self.assertFalse(target['eligible'])
		self.assertEqual(target['reason'],api.SHARED_ROW)
		with self.assertRaises(frappe.ValidationError):self.create(self.data(vehicles[0]))
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
		_,vehicles=self.receipt((1,))
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
		result=self.create(self.data(vehicles[0]))
		self.assertEqual(result['docstatus'],1)
