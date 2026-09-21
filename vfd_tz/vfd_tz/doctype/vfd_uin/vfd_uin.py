# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from vfd_tz.api.utils import get_latest_registration_doc


class VFDUIN(Document):
	def on_trash(self):
		frappe.throw(_("This document cannot be deleted"))


def get_counters(company):
	doc = ""
	if not frappe.db.exists("VFD UIN", company):
		registration_doc = get_latest_registration_doc(company)
		gc = int(registration_doc.gc) or 1
		doc = frappe.get_doc(
			{"doctype": "VFD UIN", "company": company, "gc": gc - 1, "dc": 0, "dc_date": nowdate()}
		)
		doc.insert(ignore_permissions=True)
		doc.save(ignore_permissions=True)
		doc.reload()
	else:
		doc = frappe.get_doc("VFD UIN", company)

	if doc.dc_date < getdate():
		doc.dc_date = nowdate()
		doc.dc = 0

	doc.dc += 1
	doc.gc += 1
	doc.save(ignore_permissions=True)
	doc.reload()
	return doc
