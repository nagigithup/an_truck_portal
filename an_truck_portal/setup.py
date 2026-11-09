import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from an_truck_portal.access import APP_ROLE


def _ensure_role():
	if not frappe.db.exists("Role", APP_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": APP_ROLE, "desk_access": 1}).insert()


def _ensure_custom_fields():
	create_custom_fields(
		{
			"Sales Invoice Item": [
				{
					"fieldname": "custom_center_sales_report",
					"label": "Center Sales Report",
					"fieldtype": "Link",
					"options": "Center Sales Report",
					"insert_after": "item_code",
					"read_only": 1,
					"unique": 1,
				},
			],
			"Selling Settings": [
				{
					"fieldname": "custom_spare_parts_supply_price_list",
					"label": "Spare Parts Supply Price List",
					"fieldtype": "Link",
					"options": "Price List",
					"insert_after": "selling_price_list",
				},
			],
			"Warranty Provider": [
				{
					"fieldname": "custom_sales_customer",
					"label": "Sales Customer",
					"fieldtype": "Link",
					"options": "Customer",
					"insert_after": "supplier",
				},
				{
					"fieldname": "custom_company_parts_warehouse",
					"label": "Company Parts Warehouse",
					"fieldtype": "Link",
					"options": "Warehouse",
					"insert_after": "custom_sales_customer",
					"read_only": 1,
				},
			],
			"Warranty Provider Branch": [
				{
					"fieldname": "custom_sales_customer",
					"label": "Sales Customer",
					"fieldtype": "Link",
					"options": "Customer",
					"insert_after": "warranty_provider",
				},
				{
					"fieldname": "custom_company_parts_warehouse",
					"label": "Company Parts Warehouse",
					"fieldtype": "Link",
					"options": "Warehouse",
					"insert_after": "custom_sales_customer",
					"read_only": 1,
				},
			],
		},
		ignore_validate=True,
		update=True,
	)


def after_install():
	_ensure_role()
	_ensure_custom_fields()
	ensure_single_truck_cost_fields()
	ensure_serial_revaluation_fields()


def after_migrate():
	_ensure_role()
	_ensure_custom_fields()
	ensure_single_truck_cost_fields()
	ensure_serial_revaluation_fields()


def ensure_single_truck_cost_fields():
	"""Additive audit fields only; existing vouchers and receipts are untouched."""
	create_custom_fields({"Landed Cost Voucher":[
		{"fieldname":"custom_portal_truck_cost_vehicle","label":"Single-Truck Cost Vehicle","fieldtype":"Link",
		 "options":"Vehicle Master","insert_after":"company","read_only":1,"no_copy":1,
		 "depends_on":"eval:doc.custom_portal_truck_cost_vehicle"},
		{"fieldname":"custom_portal_truck_cost_request","label":"Single-Truck Cost Request","fieldtype":"Data",
		 "hidden":1,"read_only":1,"no_copy":1,"unique":1},
		{"fieldname":"custom_portal_truck_cost_payload","label":"Single-Truck Cost Payload","fieldtype":"Data",
		 "hidden":1,"read_only":1,"no_copy":1},
	]},update=True)


def ensure_serial_revaluation_fields():
	"""Audit links on a native document and a derived VM value; no data backfill."""
	create_custom_fields({"Stock Reconciliation":[
		{"fieldname":"custom_portal_truck_cost_vehicle","label":"Single-Truck Cost Vehicle","fieldtype":"Link","options":"Vehicle Master","read_only":1,"no_copy":1},
		{"fieldname":"custom_vehicle_import_file","label":"Vehicle Import File","fieldtype":"Link","options":"Vehicle Import File","read_only":1,"no_copy":1},
		{"fieldname":"custom_portal_truck_cost_receipt","label":"Original Purchase Receipt","fieldtype":"Link","options":"Purchase Receipt","read_only":1,"no_copy":1},
		{"fieldname":"custom_portal_truck_cost_receipt_item","label":"Original Purchase Receipt Item","fieldtype":"Data","read_only":1,"no_copy":1},
		{"fieldname":"custom_portal_truck_cost_amount","label":"Requested Additional Cost","fieldtype":"Currency","options":"Company:company:default_currency","read_only":1,"no_copy":1},
		{"fieldname":"custom_portal_truck_cost_description","label":"Cost Description","fieldtype":"Small Text","read_only":1,"no_copy":1},
		{"fieldname":"custom_portal_truck_cost_request","label":"Single-Truck Cost Request","fieldtype":"Data","hidden":1,"read_only":1,"no_copy":1,"unique":1},
		{"fieldname":"custom_portal_truck_cost_payload","label":"Single-Truck Cost Payload","fieldtype":"Data","hidden":1,"read_only":1,"no_copy":1},
	],"Vehicle Master":[
		{"fieldname":"custom_portal_serial_cost_adjustment","label":"Serial Valuation Adjustment","fieldtype":"Currency","options":"cost_currency","read_only":1,"no_copy":1,"insert_after":"landed_cost_added"},
	]},update=True)
