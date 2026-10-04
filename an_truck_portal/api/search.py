import frappe
from an_truck.portal_search import search as search_records


@frappe.whitelist()
def search(q, company=None):
	"""Keep the existing endpoint contract while the backend owns search policy."""
	return search_records(q, company=company)
