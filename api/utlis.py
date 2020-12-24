# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals 
import frappe
from frappe import _
import base64
import OpenSSL
from OpenSSL import crypto
import re


def to_base64(value):
    data_bytes = value.encode('ascii')
    data = base64.b64encode(data_bytes)
    return str(data)[2:-1]


def get_signature(data, doc):
    """
    doc is registration doc
    """
    if not doc.certificate:
        return
    p12 = get_p12_certificate(doc)
    pkey = p12.get_privatekey()

    sign = OpenSSL.crypto.sign(pkey, data, "sha1") 
    data_base64 = base64.b64encode(sign)
    signenature =str(data_base64)[2:-1]

    return signenature


def get_cert_serial(registration_doc):
    if not registration_doc.certificate:
        return
    p12 = get_p12_certificate(registration_doc)
    cert = p12.get_certificate()
    cert_serial = cert.get_serial_number()
    cert_serial_hex = '{0:#0{1}x}'.format(cert_serial, 4)[2:]
    t = iter(cert_serial_hex)
    cert_serial_hex_spaced = ' '.join(a+b for a,b in zip(t, t))
    return cert_serial_hex_spaced


def get_absolute_path(file_name, is_private=False):
	from frappe.utils import cstr
	site_name = cstr(frappe.local.site)
	if(file_name.startswith('/files/')):
		file_name = file_name[7:]
	return frappe.utils.get_bench_path()+ "/sites/" + site_name  + "/" + frappe.utils.get_path('private' if is_private else 'public', 'files', file_name)[1:]
	

def get_p12_certificate(registration_doc):
    link = get_absolute_path(registration_doc.certificate, True)
    key_file = open(link, 'rb')
    key = key_file.read()
    key_file.close()
    password = registration_doc.get_password('certificate_password')
    p12 = crypto.load_pkcs12(key,password)
    return p12


def remove_special_characters(text):
    return re.sub('[^A-Za-z0-9 ]+', '', text)

def remove_all_except_numbers(text):
    return re.sub('[^0-9]+', '', text)

def get_latest_registration_doc(company):
    doc_list = frappe.get_all("VFD Registration", filters = {
        "docstatus": 1,
        "company": company,
        "r_status": "Active"
        }
    )
    if not len(doc_list):
        frappe.log_error(_("There no active VFD Registration for company ") + company)
        return
    doc = frappe.get_doc("VFD Registration", doc_list[0].name)
    return doc