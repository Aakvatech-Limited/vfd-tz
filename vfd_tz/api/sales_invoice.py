# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals 
import frappe
from frappe import _
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token
from api.xml import xml_to_dic, dict_to_xml
from api.utlis import get_signenature
import requests
from csf_tz import console


@frappe.whitelist()
def posting_vfd_invoice(invoice_name):
    doc = frappe.get_doc("Sales Invoice", invoice_name)
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
        "RCTNUM": 1,
        "DC": 2,
        "GC": 1,
        "ZNUM": str(doc.posting_date).replace("-", ""),
        "RCTVNUM": str(registration_doc.receiptcode) + str(1),
        "ITEMS": [],
        "TOTALS": {
            "TOTALTAXEXCL": doc.base_net_total,
            "TOTALTAXINCL": doc.base_total,
            "DISXOUNT": doc.base_discount_amount
        },
        "PAYMENTS": "",
        "VATTOTALS": {
            "VATRATE": "A",
            "NETTAMOUNT": doc.base_net_total,
            "TAXAMOUNT": doc.base_total - doc.base_net_total
        },
    }
    # TODO: get VATRATE from Total by Item Tax Template ? 
    # TODO : set DC & GC & RCTNUM mechanism
    for item in doc.items:
        item_data = {
            "ID": item.item_code,
            "DESC": item.item_name,
            "QTY": item.stock_qty,
            "TAXCODE": 1,  
            "AMT": item.base_amount
        }
        rect_data["ITEMS"].append(item_data)
        # TODO: Set itme TAXCODE in item Tax Template 

    rect_data_xml = dict_to_xml(rect_data, "RCT")[39:]
    console(rect_data_xml)
    efdms_data = {
        "RCT": rect_data,
        "EFDMSSIGNATURE": get_signenature(rect_data_xml, registration_doc)
    }
    data = dict_to_xml(efdms_data)
    console(data)
    url = registration_doc.url + "/efdmsRctApi/api/efdmsRctInfo"
    response = requests.request("POST", url, headers=headers, data = data, timeout=5)
    if not response.status_code == 200:
        frappe.throw(str(response.text))
    xmldict = xml_to_dic(response.text)
    console(xmldict)
    return xmldict




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
    
    data["mobile_no"] = int(mobile_no) or 0
    return data
        