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


def after_migrate():
	_ensure_role()
	_ensure_custom_fields()
