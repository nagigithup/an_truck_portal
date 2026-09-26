import hashlib
import json
import os
from urllib.parse import quote

import frappe
from frappe.sessions import get_csrf_token
from frappe.utils import get_system_timezone, now, nowdate
from frappe.utils.jinja_globals import is_rtl

from an_truck_portal import __version__
from an_truck_portal.access import can_open

no_cache = 1
sitemap = 0


def _asset_version():
	try:
		path = frappe.get_app_path("an_truck_portal", "public", "frontend", "an-truck-portal.js")
		with open(path, "rb") as handle:
			return hashlib.sha1(handle.read()).hexdigest()[:12]
	except OSError:
		return __version__


def _translations(lang):
	if not lang or lang == "en": return {}
	from frappe.translate import get_translations_from_apps
	return get_translations_from_apps(lang, apps=["an_truck_portal"])


def get_context(context):
	if frappe.session.user == "Guest":
		target = frappe.request.full_path if frappe.request else "/an-truck-portal"
		frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(target, safe="")
		raise frappe.Redirect
	lang = frappe.local.lang or "en"
	allowed = can_open()
	boot = {"csrf_token": get_csrf_token(), "user": frappe.session.user,
		"full_name": frappe.db.get_value("User", frappe.session.user, "full_name"), "allowed": allowed,
		"app_title": "AN Truck Portal", "version": __version__, "lang": lang, "rtl": is_rtl(),
		"today": nowdate(), "now": now(), "timezone": get_system_timezone(), "desk_url": "/app",
		"messages": _translations(lang) if allowed else {}}
	context.update({"lang": lang, "rtl": is_rtl(), "app_title": "AN Truck Portal", "asset_version": _asset_version(),
		"boot_json": json.dumps(boot, default=str).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")})
