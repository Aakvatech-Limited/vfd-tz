# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals 
import frappe
from frappe import _
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token
from api.xml import xml_to_dic, dict_to_xml
import requests
from csf_tz import console


@frappe.whitelist()
def vfd_invoice_posting(invoice_name):
    doc = frappe.get_doc("Sales Invoice", invoice_name)
    token_data = get_token(doc.company)
    headers = {
		'Content-Type': 'Application/xml',
        'Routing-Key': 'vfdrct',
		'Cert-Serial': token_data["cert_serial"],
		'Authorization': token_data["token"]
	}
    console(headers)
    data = {
        "date": "12-11-2020",
        "time": "12:32:00",
        "Tin": 123123,
        "Items": ""
    }
    data["Items"] = [
        {"hour":"1", "minute":"30","seconds": "40"},
        {'place': {"street":"40 something", "zip": "00000"}}
    ]
    xml = dict_to_xml(data)
    console(str(xml))