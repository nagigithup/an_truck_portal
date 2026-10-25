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


def _asset_manifest():
	root = frappe.get_app_path("an_truck_portal", "public", "frontend")
	try:
		with open(os.path.join(root, "manifest.json"), encoding="utf-8") as handle:
			manifest = json.load(handle)
		entry = manifest["src/main.js"]
		javascript = entry["file"]
		stylesheets = entry.get("css") or [
			asset["file"] for asset in manifest.values()
			if isinstance(asset, dict) and str(asset.get("file", "")).endswith(".css")
		]
		files = [javascript, *stylesheets]
		if any(os.path.isabs(path) or ".." in path.split("/") for path in files):
			raise ValueError("Invalid frontend asset path")
		version = hashlib.sha1(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12]
		return {"javascript": javascript, "stylesheets": stylesheets, "version": version}
	except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
		# Keep the page usable during a rolling deployment where the Python code
		# can become active just before the new frontend artifact is available.
		return {"javascript": "an-truck-portal.js", "stylesheets": ["an-truck-portal.css"], "version": _legacy_asset_version(root)}


def _legacy_asset_version(root):
	try:
		path = os.path.join(root, "an-truck-portal.js")
		with open(path, "rb") as handle:
			return hashlib.sha1(handle.read()).hexdigest()[:12]
	except OSError:
		return __version__


def _translations(lang):
	if not lang or lang == "en": return {}
	from frappe.translate import get_translations_from_apps
	# Warranty wording is owned by the domain app and shared by Desk and portal.
	return get_translations_from_apps(lang, apps=["an_truck", "an_truck_portal"])


def get_context(context):
	if frappe.session.user == "Guest":
		target = frappe.request.full_path if frappe.request else "/an-truck-portal"
		frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(target, safe="")
		raise frappe.Redirect
	lang = frappe.local.lang or "en"
	allowed = can_open()
	assets = _asset_manifest()
	boot = {"csrf_token": get_csrf_token(), "user": frappe.session.user,
		"full_name": frappe.db.get_value("User", frappe.session.user, "full_name"), "allowed": allowed,
		"app_title": "AN Truck Portal", "version": __version__, "asset_version": assets["version"], "lang": lang, "rtl": is_rtl(),
		"today": nowdate(), "now": now(), "timezone": get_system_timezone(), "desk_url": "/app",
		"messages": _translations(lang) if allowed else {}}
	context.update({"lang": lang, "rtl": is_rtl(), "app_title": "AN Truck Portal", "asset_version": assets["version"],
		"asset_javascript": assets["javascript"], "asset_stylesheets": assets["stylesheets"],
		"boot_json": json.dumps(boot, default=str).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")})
