# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import  now, add_to_date, now_datetime
import OpenSSL
from OpenSSL import crypto
import base64
import requests
from api.xml import xml_to_dic
import json
from csf_tz import console

class VFDRegistration(Document):
	def before_submit(self):
		self.registration()
	

	def onload(self):
		# token = get_token(self.company)
		# console(token)
		pass
	

	def on_cancel(self):
		frappe.db.set_value("VFD Registration", self.name, "r_status", "Inactive", update_modified=False)


	def registration(self):
		xmldict = get_registration(self)
		efdmsresp = xmldict.get("efdmsresp")
		if efdmsresp.get("ackcode") == "0" and efdmsresp.get("password"):
			efdmsresp["company_name"] = efdmsresp["name"]
			efdmsresp["name"] = self.name
			self.taxcodes = []
			for key, value in efdmsresp.get("taxcodes").items():
				row = self.append("taxcodes",{})
				row.tax = key
				row.tax_percent = value
			del efdmsresp["taxcodes"]
			self.update(efdmsresp)
			self.efdmssignature = xmldict.get("efdmssignature")
			self.r_status = "Active"
			self.set_active()
			frappe.msgprint(efdmsresp.get("ackmsg"),alert=True)
		else:
			frappe.throw(efdmsresp.get("ackmsg"))



	def set_active(self):
		doc_list = frappe.get_all("VFD Registration", filters = {
			"company": self.company
		})
		for doc in doc_list:
			if doc.name != self.name:
				frappe.db.set_value("VFD Registration", doc.name, "r_status", "Inactive", update_modified=False)




def get_registration(doc):
	link = get_absolute_path(doc.certificate, True)
	key_file = open(link, 'rb')
	key = key_file.read()
	key_file.close()

	password = doc.certificate_password
	p12 = crypto.load_pkcs12(key,password)
	pkey = p12.get_privatekey()

	data = "<REGDATA><TIN>{0}</TIN><CERTKEY>{1}</CERTKEY></REGDATA>".format(doc.tin, doc.certkey)
	sign = OpenSSL.crypto.sign(pkey, data, "sha1") 
	data_base64 = base64.b64encode(sign)
	data_base64 =str(data_base64)[2:-1]
	extend_data ="<?xml version=\"1.0\" encoding=\"UTF-8\"?><EFDMS>{0}<EFDMSSIGNATURE>{1}</EFDMSSIGNATURE></EFDMS>".format(data, data_base64)
	url = doc.url + "/efdmsRctApi/api/vfdRegReq"
	cert_serial_bytes = doc.cert_serial.encode('ascii')
	cert_serial = str(base64.b64encode(cert_serial_bytes))[2:-1]
	headers = {
		'Content-Type': 'application/xml',
		'Cert-Serial': cert_serial,
		'Client': "WEBAPI"
	}
	response = requests.request("POST", url, headers=headers, data = extend_data, timeout=5)
	if not response.status_code == 200:
		frappe.throw(str(response.text.encode('utf8')))
	xmldict = xml_to_dic(response.text.encode('utf8'))
	return xmldict


def get_token(company):
	doc_list = doc_list = frappe.get_all("VFD Registration", filters = {
										"docstatus": 1,
										"company": company,
										"r_status": "Active"
										})
	if not len(doc_list):
		frappe.throw(_("There no active VFD Registration for company ") + company)
	doc = frappe.get_doc("VFD Registration", doc_list[0].name)
	if doc.expires_date and doc.expires_date > now_datetime():
		return doc.access_token
	url = doc.url + "/efdmsRctApi/vfdtoken"
	data = {
	'Username': doc.username,
	'Password': doc.password,
	'grant_type': "password"
	}
	response = requests.request("POST", url, data = data, timeout=5)
	if not response.status_code == 200:
		frappe.throw(str(response.text.encode('utf8')))
	token_data =json.loads(response.text)
	doc.access_token = token_data.get("access_token")
	doc.expires_in = token_data.get("expires_in")
	doc.expires_date = add_to_date(now(),seconds= (doc.expires_in - 1000))
	doc.db_update()
	return token_data.get("access_token")


def get_absolute_path(file_name, is_private=False):
	from frappe.utils import cstr
	site_name = cstr(frappe.local.site)
	if(file_name.startswith('/files/')):
		file_name = file_name[7:]
	return frappe.utils.get_bench_path()+ "/sites/" + site_name  + "/" + frappe.utils.get_path('private' if is_private else 'public', 'files', file_name)[1:]