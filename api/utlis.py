# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals 
import frappe
from frappe import _
import base64
import OpenSSL
from OpenSSL import crypto


def to_base64(value):
    data_bytes = value.encode('ascii')
    data = base64.b64encode(data_bytes)
    return str(data)[2:-1]


def get_signature(data, doc):
    """
    doc is registration doc
    """
    link = get_absolute_path(doc.certificate, True)
    key_file = open(link, 'rb')
    key = key_file.read()
    key_file.close()

    password = doc.get_password('certificate_password')
    p12 = crypto.load_pkcs12(key,password)
    pkey = p12.get_privatekey()

    sign = OpenSSL.crypto.sign(pkey, data, "sha1") 
    data_base64 = base64.b64encode(sign)
    signenature =str(data_base64)[2:-1]

    return signenature


def get_absolute_path(file_name, is_private=False):
	from frappe.utils import cstr
	site_name = cstr(frappe.local.site)
	if(file_name.startswith('/files/')):
		file_name = file_name[7:]
	return frappe.utils.get_bench_path()+ "/sites/" + site_name  + "/" + frappe.utils.get_path('private' if is_private else 'public', 'files', file_name)[1:]
	