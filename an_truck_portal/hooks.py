app_name = "an_truck_portal"
app_title = "AN Truck Portal"
app_publisher = "AN Truck"
app_description = "Modern operational portal for truck import, purchasing, vehicles, inspection and sales"
app_email = "support@anyuanmotors.example"
app_license = "mit"

required_apps = ["erpnext", "an_truck"]
website_route_rules = [
	{"from_route": "/an-truck-portal", "to_route": "an_truck_portal"},
	{"from_route": "/an-truck-portal/<path:app_path>", "to_route": "an_truck_portal"},
]
add_to_apps_screen = [{
	"name": "an_truck_portal", "logo": "/assets/an_truck_portal/logo.svg",
	"title": "AN Truck Portal", "route": "/an-truck-portal",
	"has_permission": "an_truck_portal.access.can_open",
}]
after_install = "an_truck_portal.setup.after_install"
after_migrate = "an_truck_portal.setup.after_migrate"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "an_truck_portal",
# 		"logo": "/assets/an_truck_portal/logo.png",
# 		"title": "AN Truck Portal",
# 		"route": "/an_truck_portal",
# 		"has_permission": "an_truck_portal.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/an_truck_portal/css/an_truck_portal.css"
# app_include_js = "/assets/an_truck_portal/js/an_truck_portal.js"

# include js, css files in header of web template
# web_include_css = "/assets/an_truck_portal/css/an_truck_portal.css"
# web_include_js = "/assets/an_truck_portal/js/an_truck_portal.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "an_truck_portal/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "an_truck_portal/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "an_truck_portal.utils.jinja_methods",
# 	"filters": "an_truck_portal.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "an_truck_portal.install.before_install"
# after_install = "an_truck_portal.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "an_truck_portal.uninstall.before_uninstall"
# after_uninstall = "an_truck_portal.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "an_truck_portal.utils.before_app_install"
# after_app_install = "an_truck_portal.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "an_truck_portal.utils.before_app_uninstall"
# after_app_uninstall = "an_truck_portal.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "an_truck_portal.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "an_truck_portal.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"an_truck_portal.tasks.all"
# 	],
# 	"daily": [
# 		"an_truck_portal.tasks.daily"
# 	],
# 	"hourly": [
# 		"an_truck_portal.tasks.hourly"
# 	],
# 	"weekly": [
# 		"an_truck_portal.tasks.weekly"
# 	],
# 	"monthly": [
# 		"an_truck_portal.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "an_truck_portal.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "an_truck_portal.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "an_truck_portal.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "an_truck_portal.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["an_truck_portal.utils.before_request"]
# after_request = ["an_truck_portal.utils.after_request"]

# Job Events
# ----------
# before_job = ["an_truck_portal.utils.before_job"]
# after_job = ["an_truck_portal.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"an_truck_portal.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
