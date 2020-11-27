# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals 
import frappe, erpnext
from frappe import _
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token
from api.xml import xml_to_dic, dict_to_xml
from api.utlis import get_signature
import requests
from frappe.utils import flt
from vfd_tz.vfd_tz.doctype.vfd_uin.vfd_uin import get_counters
from frappe.utils.background_jobs import enqueue
import json
from csf_tz import console


@frappe.whitelist()
def enqueue_posting_vfd_invoice(invoice_name):
        enqueue(method=posting_vfd_invoice, queue='short', timeout=10000, is_async=True , kwargs=invoice_name )
        frappe.msgprint(_("Start Sending Invoice to VFD"),alert=True)
        return True


def posting_vfd_invoice(kwargs):
    invoice_name = kwargs
    doc = frappe.get_doc("Sales Invoice", invoice_name)
    if doc.vfd_posting_info or doc.docstatus != 1:
        return
    if doc.vfd_status == "Not Sent":
        doc.vfd_status = "Pending"
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

    if not doc.taxes_and_charges:
        doc.vfd_status = "Failed"
        doc.db_update()
        frappe.db.commit()
        frappe.throw(_("Sales Taxes and Charges Template not set for Invoice Number {0}".format(doc.name)))
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

    for item in doc.items:
        if not item.item_tax_template:
            doc.vfd_status = "Failed"
            doc.db_update()
            frappe.db.commit()
            frappe.throw(_("Item Taxes Template not set for item {0}".format(item.item_code)))
        item_data = {
            "ID": item.item_code,
            "DESC": item.item_name,
            "QTY": flt(item.stock_qty,2),
            "TAXCODE": get_item_taxcode(item.item_tax_template, doc.taxes_and_charges),  
            "AMT": flt(item.base_amount,2)
        }
        rect_data["ITEMS"].append({"ITEM":item_data})

    if not doc.vfd_rctnum:
        counters = get_counters(doc.company)
        doc.vfd_gc = counters.gc
        doc.vfd_rctnum = counters.gc
        doc.vfd_dc = counters.dc
        doc.db_update()
        frappe.db.commit()
        doc.reload()
        rect_data["RCTNUM"] = doc.vfd_gc
        rect_data["DC"] = doc.vfd_dc
        rect_data["GC"] = doc.vfd_gc
        rect_data["RCTVNUM"] = str(registration_doc.receiptcode) + str(doc.vfd_gc)

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
        doc.vfd_status = "Success"
        doc.db_update()
        frappe.db.commit()
    else:
        doc.vfd_status = "Failed"
        doc.db_update()
        frappe.db.commit()


def get_invoice_taxes(doc, method=None):
    data = get_itemised_tax_breakup_html(doc)
    console(data)
    


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


def get_item_taxcode(item_tax_template=None, taxes_and_charges=None):
    taxcode = 0
    if item_tax_template:
        vfd_taxcode = frappe.get_value("Item Tax Template", item_tax_template, "vfd_taxcode")
        if vfd_taxcode:
            taxcode = int(vfd_taxcode[:1])
        else:
            frappe.throw(_("VFD Tax Code not setup in {0}".format(item_tax_template)))
    elif taxes_and_charges:
        vatrate = get_vatrate(taxes_and_charges)
        taxes_map = {
            "A": "1",
            "B": "2",
            "C": "3",
            "D": "4",
            "E": "5"
        }
        taxcode = taxes_map.get(vatrate)
    return taxcode


def get_vatrate(taxes_and_charges = None):
    vatrate = ""
    if taxes_and_charges:
        vfd_vatrate = frappe.get_value("Sales Taxes and Charges Template", taxes_and_charges, "vfd_vatrate")
        if vfd_vatrate:
            vatrate = vfd_vatrate[:1]
        else:
            frappe.throw(_("VFD VAT Rate not setup in {0}".format(taxes_and_charges)))
    return vatrate


def get_payments(payments, base_total):
    payments_dict = []
    total_payments_amount = 0
    for payment in payments:
        pmttype = ""
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



def posting_all_vfd_invoices():
    invoices_list = frappe.get_all("Sales Invoice", filters = {
        "docstatus": 1,
        "vfd_posting_info": ["in", ["", None]],
        "vfd_rctnum": ["not in", ["", None]]
    })
    for invoice in invoices_list:
        count_list = frappe.get_all("VFD Invoice Posting Info", filters= {"sales_invoice": invoice.name})
        if len(count_list) < 6:
            enqueue_posting_vfd_invoice(invoice.name)
    

def validate_cancel(doc, method):
    if doc.vfd_rctnum:
        frappe.throw(_("This invoice cannot be canceled"))


def get_itemised_tax_breakup_html(doc):
	if not doc.taxes:
		return
	frappe.flags.company = doc.company

	# get headers
	tax_accounts = []
	for tax in doc.taxes:
		if getattr(tax, "category", None) and tax.category=="Valuation":
			continue
		if tax.description not in tax_accounts:
			tax_accounts.append(tax.description)

	headers = get_itemised_tax_breakup_header(doc.doctype + " Item", tax_accounts)

	# get tax breakup data
	itemised_tax, itemised_taxable_amount = get_itemised_tax_breakup_data(doc)

	get_rounded_tax_amount(itemised_tax, doc.precision("tax_amount", "taxes"))

	return dict(
			headers=headers,
			itemised_tax=itemised_tax,
			itemised_taxable_amount=itemised_taxable_amount,
			tax_accounts=tax_accounts,
		)


@erpnext.allow_regional
def get_itemised_tax_breakup_header(item_doctype, tax_accounts):
	return [_("Item"), _("Taxable Amount")] + tax_accounts


@erpnext.allow_regional
def get_itemised_tax_breakup_data(doc):
	itemised_tax = get_itemised_tax(doc.taxes)

	itemised_taxable_amount = get_itemised_taxable_amount(doc.items)

	return itemised_tax, itemised_taxable_amount


def get_itemised_tax(taxes, with_tax_account=False):
	itemised_tax = {}
	for tax in taxes:
		if getattr(tax, "category", None) and tax.category=="Valuation":
			continue

		item_tax_map = json.loads(tax.item_wise_tax_detail) if tax.item_wise_tax_detail else {}
		if item_tax_map:
			for item_code, tax_data in item_tax_map.items():
				itemised_tax.setdefault(item_code, frappe._dict())

				tax_rate = 0.0
				tax_amount = 0.0

				if isinstance(tax_data, list):
					tax_rate = flt(tax_data[0])
					tax_amount = flt(tax_data[1])
				else:
					tax_rate = flt(tax_data)

				itemised_tax[item_code][tax.description] = frappe._dict(dict(
					tax_rate = tax_rate,
					tax_amount = tax_amount
				))

				if with_tax_account:
					itemised_tax[item_code][tax.description].tax_account = tax.account_head

	return itemised_tax


def get_rounded_tax_amount(itemised_tax, precision):
	# Rounding based on tax_amount precision
	for taxes in itemised_tax.values():
		for tax_account in taxes:
			taxes[tax_account]["tax_amount"] = flt(taxes[tax_account]["tax_amount"], precision)


def get_itemised_taxable_amount(items):
	itemised_taxable_amount = frappe._dict()
	for item in items:
		item_code = item.item_code or item.item_name
		itemised_taxable_amount.setdefault(item_code, 0)
		itemised_taxable_amount[item_code] += item.net_amount

	return itemised_taxable_amount
