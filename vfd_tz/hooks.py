# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "vfd_tz"
app_title = "vfd-tz"
app_publisher = "Aakvatech"
app_description = "VFD TZ"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@aakvatech.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/vfd_tz/css/vfd_tz.css"
# app_include_js = "/assets/vfd_tz/js/vfd_tz.js"

# include js, css files in header of web template
# web_include_css = "/assets/vfd_tz/css/vfd_tz.css"
# web_include_js = "/assets/vfd_tz/js/vfd_tz.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Sales Invoice" : "api/sales_invoice.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "vfd_tz.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "vfd_tz.install.before_install"
# after_install = "vfd_tz.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "vfd_tz.notifications.get_notification_config"

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
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"vfd_tz.tasks.all"
# 	],
# 	"daily": [
# 		"vfd_tz.tasks.daily"
# 	],
# 	"hourly": [
# 		"vfd_tz.tasks.hourly"
# 	],
# 	"weekly": [
# 		"vfd_tz.tasks.weekly"
# 	]
# 	"monthly": [
# 		"vfd_tz.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "vfd_tz.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "vfd_tz.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "vfd_tz.task.get_dashboard_data"
# }

fixtures = [
	{"doctype":"Custom Field", "filters": [["name", "in", (
        "Customer-vfd_custid",
        "Customer-vfd_custidtype",
		"Mode of Payment-vfd_pmttype",
		"Sales Taxes and Charges Template-vfd_vatrate",
		"Item Tax Template-vfd_taxcode",
		"Sales Invoice-vfd_gc",
		"Sales Invoice-vfd_dc",
		"Sales Invoice-vfd_rctnum",
		"Sales Invoice-vfd_posting_info"
	)]]},
	{"doctype":"Property Setter", "filters": [["name", "in", (
	
	)]]},
]
