# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.background_jobs import enqueue_doc
import OpenSSL
from OpenSSL import crypto
import base64
import requests
from api.xml import xml_to_dic
from api.utils import to_base64, get_signature, get_cert_serial
from frappe.utils.password import set_encrypted_password


class VFDRegistration(Document):
    def validate(self):
        cert_serial = get_cert_serial(self)
        self.cert_serial = cert_serial

    def before_submit(self):
        self.registration()

    def onload(self):
        pass

    def on_cancel(self):
        frappe.db.set_value(
            "VFD Registration", self.name, "r_status", "Inactive", update_modified=False
        )

    def registration(self):
        xmldict = get_registration(self)
        efdmsresp = xmldict.get("efdmsresp")
        if efdmsresp.get("ackcode") == "0" and efdmsresp.get("password"):
            efdmsresp["company_name"] = efdmsresp["name"]
            efdmsresp["name"] = self.name
            self.taxcodes = []
            for key, value in efdmsresp.get("taxcodes").items():
                row = self.append("taxcodes", {})
                row.tax = key
                row.tax_percent = value
            del efdmsresp["taxcodes"]
            self.update(efdmsresp)
            self.efdmssignature = xmldict.get("efdmssignature")
            self.r_status = "Active"
            self.set_active()
            frappe.msgprint(efdmsresp.get("ackmsg"), alert=True)
        else:
            frappe.throw(efdmsresp.get("ackmsg"))

    def set_active(self):
        doc_list = frappe.get_all("VFD Registration", filters={"company": self.company})
        for doc in doc_list:
            if doc.name != self.name:
                frappe.db.set_value(
                    "VFD Registration",
                    doc.name,
                    "r_status",
                    "Inactive",
                    update_modified=False,
                )


def get_registration(doc):
    data = "<REGDATA><TIN>{0}</TIN><CERTKEY>{1}</CERTKEY></REGDATA>".format(
        doc.tin, doc.get_password("certkey")
    )
    signenature = get_signature(data, doc)
    extend_data = '<?xml version="1.0" encoding="UTF-8"?><EFDMS>{0}<EFDMSSIGNATURE>{1}</EFDMSSIGNATURE></EFDMS>'.format(
        data, signenature
    )
    url = doc.url + "/api/vfdRegReq"
    cert_serial = to_base64(doc.cert_serial)
    headers = {
        "Content-Type": "application/xml",
        "Cert-Serial": cert_serial,
        "Client": "WEBAPI",
    }
    response = requests.request(
        "POST", url, headers=headers, data=extend_data, timeout=5
    )
    if not response.status_code == 200:
        frappe.throw(str(response.text.encode("utf8")))
    xmldict = xml_to_dic(response.text.encode("utf8"))
    return xmldict


def auto_reregistration(doc=None, doc_name=None):
    if not doc:
        if doc_name:
            doc = frappe.get_doc("VFD Registration", doc_name)
        else:
            frappe.throw(_("No VFD Registration document supplied"))
    new_doc = frappe.copy_doc(doc)
    new_doc.certkey = doc.get_password("certkey")
    new_doc.certificate_password = doc.get_password("certificate_password")
    new_doc.docstatus = 0
    new_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    # enqueue_doc(
    #     new_doc.doctype,
    #     name=new_doc.name,
    #     method="submit",
    #     queue="default",
    #     timeout=300,
    # )
