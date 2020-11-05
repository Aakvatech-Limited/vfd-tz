# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, getdate
from frappe import _

class VFDUIN(Document):
	def on_trash(self):
		frappe.throw(_("This document cannot be deleted"))


def get_counters(company):
	doc = ""
	if not frappe.db.exists("VFD UIN", company):
		doc = frappe.get_doc({
			"doctype" : "VFD UIN",
			"company": company,
			"gc": 0,
			"dc": 0,
			"dc_date" : nowdate()
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		doc.reload()
	else:
		doc = frappe.get_doc("VFD UIN", company)
	
	if doc.dc_date < getdate():
		doc.dc_date = nowdate()
		doc.dc = 0
	
	doc.dc += 1
	doc.gc += 1
	doc.save()
	frappe.db.commit()
	return doc