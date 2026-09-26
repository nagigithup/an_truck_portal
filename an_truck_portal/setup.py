import frappe

from an_truck_portal.access import APP_ROLE


def _ensure_role():
	if not frappe.db.exists("Role", APP_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": APP_ROLE, "desk_access": 1}).insert()


def after_install():
	_ensure_role()


def after_migrate():
	_ensure_role()
