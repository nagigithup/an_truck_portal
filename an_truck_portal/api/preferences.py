import frappe
from an_truck_portal.access import require_access


@frappe.whitelist(methods=["POST"])
def set_language(language):
	require_access()
	value = language if language in {"ar", "en"} else "ar"
	frappe.defaults.set_user_default("an_truck_portal_language", value, user=frappe.session.user)
	return value
