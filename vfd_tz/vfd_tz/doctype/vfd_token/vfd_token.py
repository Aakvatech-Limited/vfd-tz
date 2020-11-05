# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import  now, add_to_date, now_datetime
from api.utlis import to_base64
import requests
import json

class VFDToken(Document):
	pass


def get_token(company):
	token_data = {}
	doc_list = doc_list = frappe.get_all("VFD Registration", filters = {
										"docstatus": 1,
										"company": company,
										"r_status": "Active"
										})
	if not len(doc_list):
		frappe.throw(_("There no active VFD Registration for company ") + company)
	doc = frappe.get_doc("VFD Registration", doc_list[0].name)
	token_data["cert_serial"] = to_base64(doc.get_password('cert_serial'))
	token_data["doc"] = doc
	
	token_list = frappe.get_all("VFD Token", 
										filters = {
											"docstatus": 1,
											"company": company,
											"vfd_registration": doc_list[0].name,
											"expires_date": [">", now_datetime()]
										}, 
										fields = ["name", "access_token"]
										)

	if len(token_list):
		token_data["token"] = "bearer " + token_list[0]["access_token"] 
	
	else:
		url = doc.url + "/efdmsRctApi/vfdtoken"
		data = {
			'Username': doc.get_password('username'),
			'Password': doc.get_password('password'),
			'grant_type': "password"
		}
		response = requests.request("POST", url, data = data, timeout=5)
		if not response.status_code == 200:
			frappe.throw(str(response.text.encode('utf8')))
		token_data =json.loads(response.text)
		token_doc = frappe.get_doc({
			"doctype" : "VFD Token",
			"company" : doc.company,
			"vfd_registration" : doc.name,
			"posting_date" : now_datetime(),
			"expires_in" : int(token_data.get("expires_in")),
			"expires_date" : add_to_date(now(), seconds = (int(token_data.get("expires_in")) - 1000)),
			"access_token" : token_data.get("access_token")
		})

		token_doc.flags.ignore_permissions=True
		token_doc.insert(ignore_permissions=True)
		token_doc.submit()
		frappe.db.commit()
		token_data["token"] = "bearer " + token_data.get("access_token")
	
	return token_data