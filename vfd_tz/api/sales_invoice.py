# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals 
import frappe
from frappe import _
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token
from api.xml import xml_to_dic, dict_to_xml
from api.utlis import get_signature
import requests
from frappe.utils import flt
from vfd_tz.vfd_tz.doctype.vfd_uin.vfd_uin import get_counters


@frappe.whitelist()
def posting_vfd_invoice(invoice_name):
    doc = frappe.get_doc("Sales Invoice", invoice_name)
    if doc.vfd_posting_info or doc.docstatus != 1:
        return
    if not doc.vfd_rctnum:
        counters = get_counters(doc.company)
        doc.vfd_gc = counters.gc
        doc.vfd_rctnum = counters.gc
        doc.vfd_dc = counters.dc
        doc.db_update()
        frappe.db.commit()
        doc.reload()
    token_data = get_token(doc.company)
    registration_doc = token_data.get("doc")
    headers = {
        'Content-Type': 'Application/xml',
        'Routing-Key': 'vfdrct',
        'Cert-Serial': token_data["cert_serial"],
        'Authorization': token_data["token"]
    }
    customer_id_info = get_customer_id_info(doc.customer)

    rect_data = {
        "DATE": doc.posting_date,
        "TIME": str(doc.posting_time)[0:-7],
        "TIN": registration_doc.tin,
        "REGID": registration_doc.regid,
        "EFDSERIAL": registration_doc.serial,
        "CUSTIDTYPE": customer_id_info["cust_id_type"],
        "CUSTID": customer_id_info["cust_id"],
        "CUSTNAME": doc.customer,
        "MOBILENUM": customer_id_info["mobile_no"],
        "RCTNUM": doc.vfd_gc,
        "DC": doc.vfd_dc,
        "GC": doc.vfd_gc,
        "ZNUM": str(doc.posting_date).replace("-", ""),
        "RCTVNUM": str(registration_doc.receiptcode) + str(doc.vfd_gc),
        "ITEMS": [],
        "TOTALS": {
            "TOTALTAXEXCL": flt(doc.base_net_total,2),
            "TOTALTAXINCL": flt(doc.base_total,2),
            "DISCOUNT": flt(doc.base_discount_amount,2)
        },
        "PAYMENTS": get_payments(doc.payments, doc.base_total),
        "VATTOTALS": {
            "VATRATE": get_vatrate(doc.taxes_and_charges),
            "NETTAMOUNT": flt(doc.base_net_total,2),
            "TAXAMOUNT": flt(flt(doc.base_total,2) - flt(doc.base_net_total,2), 2)
        },
    }

    # TODO : set DC & GC & RCTNUM mechanism
    for item in doc.items:
        item_data = {
            "ID": item.item_code,
            "DESC": item.item_name,
            "QTY": flt(item.stock_qty,2),
            "TAXCODE": get_item_taxcode(item.item_tax_template),  
            "AMT": flt(item.base_amount,2)
        }
        rect_data["ITEMS"].append({"ITEM":item_data})

    rect_data_xml = str(dict_to_xml(rect_data, "RCT")[39:]).replace("<None>", "").replace("</None>", "")

    efdms_data = {
        "RCT": rect_data,
        "EFDMSSIGNATURE": get_signature(rect_data_xml, registration_doc)
    }
    data = dict_to_xml(efdms_data).replace("<None>", "").replace("</None>", "")
    url = registration_doc.url + "/efdmsRctApi/api/efdmsRctInfo"
    response = requests.request("POST", url, headers=headers, data = data, timeout=5)
    if not response.status_code == 200:
        frappe.throw(str(response.text))
    xmldict = xml_to_dic(response.text)
    rctack = xmldict.get("rctack")
    posting_info_doc = frappe.get_doc({
        "doctype" : "VFD Invoice Posting Info",
        "sales_invoice" : doc.name,
        "ackcode" : rctack.get("ackcode"),
        "ackmsg" : rctack.get("ackmsg"),
        "date" : rctack.get("date"),
        "time" : rctack.get("time"),
        "rctnum": rctack.get("rctnum"),
        "efdmssignature" : xmldict.get("efdmssignature"),
        "req_headers": str(headers),
        "req_data": str(data).encode('utf8')
	})
    posting_info_doc.flags.ignore_permissions=True
    posting_info_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    if int(posting_info_doc.ackcode) == 0:
        doc.vfd_posting_info = posting_info_doc.name
        doc.db_update()
        frappe.db.commit()
    frappe.msgprint(rctack.get("ackmsg"),alert=True)




def get_customer_id_info(customer):
    data = {}
    cust_id, cust_id_type, mobile_no = frappe.get_value("Customer", customer, ["vfd_custid", "vfd_custidtype", "mobile_no"])
    if not cust_id:
        data["cust_id"] = ""
        data["cust_id_type"] = 6
    elif cust_id and not cust_id_type:
        frappe.throw(_("Please make sure to set VFD Customer ID Type in Customer Master"))
    else:
        data["cust_id"] = cust_id
        data["cust_id_type"] = int(cust_id_type[:1])
    
    data["mobile_no"] = int(mobile_no or 0)
    return data


def get_item_taxcode(item_tax_template = None):
    taxcode = 0
    if not item_tax_template:
        ## NOTE : how we shold handle if there no item_tax_template in item
        taxcode = 3
    else:
        vfd_taxcode = frappe.get_value("Item Tax Template", item_tax_template, "vfd_taxcode")
        if vfd_taxcode:
            taxcode = int(vfd_taxcode[:1])
        else:
            taxcode = 3
    return taxcode


def get_vatrate(taxes_and_charges = None):
    vatrate = ""
    if not taxes_and_charges:
        ## NOTE : how we shold handle if there no taxes_and_charges in sales invoice
        vatrate = "C"
    else:
        vfd_vatrate = frappe.get_value("Sales Taxes and Charges Template", taxes_and_charges, "vfd_vatrate")
        if vfd_vatrate:
            vatrate = vfd_vatrate[:1]
        else:
            vatrate = "C"
    return vatrate


def get_payments(payments, base_total):
    payments_dict = []
    total_payments_amount = 0
    for payment in payments:
        pmttype = "CASH"
        vfd_pmttype = frappe.get_value("Mode of Payment", payment.mode_of_payment, "vfd_pmttype")
        if vfd_pmttype:
            pmttype = vfd_pmttype
        total_payments_amount += payment.base_amount
        payments_dict.append({"PMTTYPE": pmttype})
        payments_dict.append({"PMTAMOUNT": flt(payment.base_amount,2)})
    
    if base_total > total_payments_amount:
        payments_dict.append({"PMTTYPE": "INVOICE"})
        payments_dict.append({"PMTAMOUNT": flt(base_total - total_payments_amount,2)})
     
    return payments_dict