import frappe
from frappe import _

APP_ROLE = "AN Truck Portal User"


def can_open(user=None):
	user = user or frappe.session.user
	return bool(user and user != "Guest" and (APP_ROLE in frappe.get_roles(user) or "System Manager" in frappe.get_roles(user)))


def require_access():
	if frappe.session.user == "Guest":
		frappe.throw(_("Sign in to use AN Truck Portal."), frappe.AuthenticationError)
	if not can_open():
		frappe.throw(_("You do not have access to AN Truck Portal."), frappe.PermissionError)


def require_read(doctype):
	require_access()
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted to read {0}.").format(_(doctype)), frappe.PermissionError)
