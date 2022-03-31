# -*- coding: utf-8 -*-
# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import erpnext
from frappe import _
from vfd_tz.vfd_tz.doctype.vfd_token.vfd_token import get_token
from api.xml import xml_to_dic, dict_to_xml
from api.utlis import (
    get_signature,
    remove_special_characters,
    get_latest_registration_doc,
    remove_all_except_numbers,
)
import requests
from frappe.utils import flt, nowdate, nowtime, format_datetime
from vfd_tz.vfd_tz.doctype.vfd_uin.vfd_uin import get_counters
from frappe.utils.background_jobs import enqueue
import json
import time


def vfd_validation(doc, method):
    if doc.is_return or doc.is_not_vfd_invoice:
        return
    if doc.base_net_total == 0:
        frappe.throw(_("Base net amount is zero. Correct the invoice and retry."))

    tax_data = get_itemised_tax_breakup_html(doc)
    if not tax_data:
        frappe.throw(_("Taxes not set correctly"))

    for item in doc.items:
        if not item.item_code:
            frappe.throw(_("Item Code not set for item {0}".format(item.item_name)))
        if not item.item_tax_template:
            item_tax_template = frappe.get_value(
                "Item", item.item_code, "default_tax_template"
            )
            if not item_tax_template:
                frappe.throw(
                    _("Item Taxes Template not set for item {0}".format(item.item_code))
                )
            else:
                item.item_tax_template = item_tax_template
        item_taxcode = get_item_taxcode(
            item.item_tax_template, item.item_code, doc.name
        )

        with_tax = 0
        other_tax = 0

        for tax_name, tax_value in tax_data.get(item.item_code).items():
            if tax_value.get("tax_rate") == 18:
                with_tax += 1
            else:
                other_tax += tax_value.get("tax_amount")

        if other_tax:
            frappe.throw(
                _(
                    "Taxes not set correctly for Other Tax item {0}".format(
                        item.item_code
                    )
                )
            )
        if item_taxcode == 1 and with_tax != 1:
            frappe.throw(
                _(
                    "Taxes not set correctly for Standard Rate item {0}".format(
                        item.item_code
                    )
                )
            )
        elif item_taxcode != 1 and with_tax != 0:
            frappe.throw(
                _(
                    "Taxes not set correctly for Non Standard Rate item {0}".format(
                        item.item_code
                    )
                )
            )


@frappe.whitelist()
def enqueue_posting_vfd_invoice(invoice_name):
    doc = frappe.get_doc("Sales Invoice", invoice_name)
    if doc.is_return or doc.is_not_vfd_invoice:
        return
    registration_doc = get_latest_registration_doc(doc.company)
    if not registration_doc.vfd_start_date:
        frappe.throw(
            _(
                "VFD Start Date not set in VFD Registration. Please set it in VFD Registration"
            )
        )
    if doc.creation < registration_doc.vfd_start_date:
        frappe.throw(
            _(
                "Sales Invoice creation older than VFD Registration date! Cannot submit VFD to TRA."
            )
        )
    if doc.posting_date < registration_doc.vfd_start_date.date():
        frappe.throw(
            _(
                "Sales Invoice posting date older than VFD Registration date! Cannot submit VFD to TRA."
            )
        )
    if not doc.vfd_rctnum:
        counters = get_counters(doc.company)
        doc.vfd_gc = counters.gc
        doc.vfd_rctnum = counters.gc
        doc.vfd_dc = counters.dc
        doc.vfd_date = nowdate()
        doc.vfd_time = nowtime()
        doc.vfd_rctvnum = str(registration_doc.receiptcode) + str(doc.vfd_gc)
        doc.vfd_verification_url = registration_doc.verification_url + doc.vfd_rctvnum
        if doc.vfd_status == "Not Sent":
            doc.vfd_status = "Pending"
        doc.db_update()
        frappe.db.commit()
        frappe.msgprint(_("Registered Invoice to be sent to TRA VFD System"))
    if not frappe.local.flags.vfd_posting:
        enqueue(
            method=posting_all_vfd_invoices, queue="short", timeout=10000, is_async=True
        )
    return True


def posting_all_vfd_invoices():
    if frappe.local.flags.vfd_posting:
        return
    frappe.local.flags.vfd_posting = True
    company_list = frappe.get_all("Company")
    for company in company_list:
        registration_doc = get_latest_registration_doc(company["name"])
        if not registration_doc:
            continue
        if registration_doc.do_not_send_vfd:
            continue
        invoices_list = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "is_return": 0,
                "company": company.name,
                "vfd_posting_info": ["in", ["", None]],
                "vfd_status": ["in", ["Failed", "Pending"]],
            },
            fields={"name", "vfd_rctnum", "vfd_gc"},
            order_by="vfd_gc ASC",
        )
        # Find out last invoice to ensure next GC is correctly sent
        last_invoices_list = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "is_return": 0,
                "company": company.name,
                "vfd_posting_info": ["not in", ["", None]],
                "vfd_status": ["in", ["Success"]],
            },
            fields={"name", "vfd_rctnum", "vfd_gc"},
            page_length=10,
            order_by="vfd_gc DESC",
        )

        first_to_send_gc = 0
        last_sent_success_gc = 0

        if len(invoices_list) > 0:
            first_to_send_gc = invoices_list[0].get("vfd_gc")
        else:
            continue
        if len(last_invoices_list) > 0:
            last_sent_success_gc = last_invoices_list[0].get("vfd_gc")
        else:
            last_sent_success_gc = int(registration_doc.gc) - 1

        if last_sent_success_gc + 1 != first_to_send_gc:
            frappe.throw(
                _(
                    "Invoice sequence out of order. Last GC Sent Successfully is {0}. First to send GC is {1}. Check failed VFD Invoice Posting Info"
                ).format(last_sent_success_gc, first_to_send_gc)
            )

        for invoice in invoices_list:
            status = posting_vfd_invoice(invoice.name)
            if status != "Success":
                frappe.local.flags.vfd_posting = False
                frappe.throw(_("Error in sending VFD Invoice {0}").format(invoice.name))
                break
        frappe.local.flags.vfd_posting = False


def posting_vfd_invoice(invoice_name):
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
        "Content-Type": "Application/xml",
        "Routing-Key": "vfdrct",
        "Cert-Serial": token_data["cert_serial"],
        "Authorization": token_data["token"],
    }
    customer_id_info = get_customer_id_info(doc.customer)
    if not doc.vfd_cust_id:
        vfd_cust_id_type = str(customer_id_info["cust_id_type"])
        vfd_cust_id = customer_id_info["cust_id"]
    elif doc.vfd_cust_id and not doc.vfd_cust_id_type:
        frappe.throw(
            _("Please make sure to set VFD Customer ID Type in Customer Master")
        )
    else:
        vfd_cust_id_type = doc.vfd_cust_id_type
        vfd_cust_id = doc.vfd_cust_id

    rect_data = {
        "DATE": doc.vfd_date,
        # 0:59:30.715164
        "TIME": format_datetime(str(doc.vfd_time), "HH:mm:ss"),
        "TIN": registration_doc.tin,
        "REGID": registration_doc.regid,
        "EFDSERIAL": registration_doc.serial,
        "CUSTIDTYPE": int(vfd_cust_id_type[:1]),
        "CUSTID": vfd_cust_id,
        "CUSTNAME": remove_special_characters(doc.customer),
        "MOBILENUM": customer_id_info["mobile_no"],
        "RCTNUM": doc.vfd_gc,
        "DC": doc.vfd_dc,
        "GC": doc.vfd_gc,
        "ZNUM": format_datetime(str(doc.vfd_date), "YYYYMMdd"),
        "RCTVNUM": doc.vfd_rctvnum,
        "ITEMS": [],
        "TOTALS": {
            "TOTALTAXEXCL": flt(doc.base_net_total, 2),
            "TOTALTAXINCL": flt(doc.base_grand_total, 2),
            "DISCOUNT": flt(doc.base_discount_amount, 2),
        },
        "PAYMENTS": get_payments(doc.payments, doc.base_total),
        "VATTOTALS": get_vattotals(doc.items, doc.name),
    }
    use_item_group = registration_doc.use_item_group
    for item in doc.items:
        item_data = {
            "ID": remove_special_characters(
                item.item_group if use_item_group else item.item_code
            ),
            "DESC": remove_special_characters(
                item.item_group if use_item_group else item.item_name
            ),
            "QTY": flt(item.stock_qty, 2),
            "TAXCODE": get_item_taxcode(
                item.item_tax_template, item.item_code, doc.name
            ),
            "AMT": flt(get_item_inclusive_amount(item), 2),
        }
        if use_item_group:
            found_item = ""
            for i in rect_data["ITEMS"]:
                if (
                    i["ITEM"]["TAXCODE"] == item_data["TAXCODE"]
                    and i["ITEM"]["ID"] == item_data["ID"]
                ):
                    found_item = i["ITEM"]
                    break
            if found_item:
                found_item["QTY"] = 1
                rounded_amount = flt(found_item["AMT"], 2)
                found_item["AMT"] = flt(rounded_amount, 2) + flt(item_data["AMT"], 2)
            else:
                item_data["QTY"] = 1
                rect_data["ITEMS"].append({"ITEM": item_data})
        else:
            rect_data["ITEMS"].append({"ITEM": item_data})

    rect_data_xml = (
        str(dict_to_xml(rect_data, "RCT")[39:])
        .replace("<None>", "")
        .replace("</None>", "")
    )

    efdms_data = {
        "RCT": rect_data,
        "EFDMSSIGNATURE": get_signature(rect_data_xml, registration_doc),
    }
    data = dict_to_xml(efdms_data).replace("<None>", "").replace("</None>", "")
    url = registration_doc.url + "/api/efdmsRctInfo"
    response = requests.request("POST", url, headers=headers, data=data, timeout=5)

    if not response.status_code == 200:
        posting_info_doc = frappe.get_doc(
            {
                "doctype": "VFD Invoice Posting Info",
                "sales_invoice": doc.name,
                "ackcode": response.status_code,
                "ackmsg": response.text,
                "date": nowdate(),
                "time": nowtime(),
                "req_headers": str(headers),
                "req_data": str(data).encode("utf8"),
            }
        )
        doc.vfd_status = "Failed"
        doc.db_update()
        frappe.db.commit()
        return "Failed"

    xmldict = xml_to_dic(response.text)
    rctack = xmldict.get("rctack")
    posting_info_doc = frappe.get_doc(
        {
            "doctype": "VFD Invoice Posting Info",
            "sales_invoice": doc.name,
            "ackcode": rctack.get("ackcode"),
            "ackmsg": rctack.get("ackmsg"),
            "date": rctack.get("date"),
            "time": rctack.get("time"),
            "rctnum": rctack.get("rctnum"),
            "efdmssignature": xmldict.get("efdmssignature"),
            "req_headers": str(headers),
            "req_data": str(data).encode("utf8"),
        }
    )
    posting_info_doc.flags.ignore_permissions = True
    posting_info_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    if int(posting_info_doc.ackcode) == 0:
        doc.vfd_posting_info = posting_info_doc.name
        doc.vfd_status = "Success"
        doc.db_update()
        frappe.db.commit()
        return "Success"
    else:
        doc.vfd_status = "Failed"
        doc.db_update()
        frappe.db.commit()
        return "Failed"


def get_customer_id_info(customer):
    data = {}
    cust_id, cust_id_type, mobile_no = frappe.get_value(
        "Customer", customer, ["vfd_custid", "vfd_custidtype", "mobile_no"]
    )
    if not cust_id:
        data["cust_id"] = ""
        data["cust_id_type"] = 6
    elif cust_id and not cust_id_type:
        frappe.throw(
            _("Please make sure to set VFD Customer ID Type in Customer Master")
        )
    else:
        data["cust_id"] = cust_id
        data["cust_id_type"] = int(cust_id_type[:1])

    data["mobile_no"] = remove_all_except_numbers(mobile_no) or ""
    return data


def get_item_taxcode(item_tax_template=None, item_code=None, invoice_name=None):
    if not item_tax_template:
        if item_code and invoice_name:
            frappe.throw(
                _(
                    "Item Taxes Template not set for item {0} in invoice {1}".format(
                        item_code, invoice_name
                    )
                )
            )
        elif item_code:
            frappe.throw(
                _("Item Taxes Template not set for item {0}".format(item_code))
            )
        else:
            frappe.throw(_("Item Taxes Template not set"))

    taxcode = None
    if item_tax_template:
        vfd_taxcode = frappe.get_value(
            "Item Tax Template", item_tax_template, "vfd_taxcode"
        )
        if vfd_taxcode:
            taxcode = int(vfd_taxcode[:1])
        else:
            frappe.throw(_("VFD Tax Code not setup in {0}".format(item_tax_template)))
    return taxcode


def get_payments(payments, base_total):
    payments_dict = []
    total_payments_amount = 0
    for payment in payments:
        pmttype = ""
        vfd_pmttype = frappe.get_value(
            "Mode of Payment", payment.mode_of_payment, "vfd_pmttype"
        )
        if vfd_pmttype:
            pmttype = vfd_pmttype
        else:
            frappe.throw(
                _(
                    "VFD Payment Type in Mode of Payment not setup in {0}".format(
                        payment.mode_of_payment
                    )
                )
            )
        total_payments_amount += payment.base_amount
        payments_dict.append({"PMTTYPE": pmttype})
        payments_dict.append({"PMTAMOUNT": flt(payment.base_amount, 2)})

    if base_total > total_payments_amount:
        payments_dict.append({"PMTTYPE": "INVOICE"})
        payments_dict.append({"PMTAMOUNT": flt(base_total - total_payments_amount, 2)})

    return payments_dict


def get_vattotals(items, invoice_name):
    vattotals = {}
    for item in items:
        item_taxcode = get_item_taxcode(
            item.item_tax_template, item.item_code, invoice_name
        )
        if not vattotals.get(item_taxcode):
            vattotals[item_taxcode] = {}
            vattotals[item_taxcode]["NETTAMOUNT"] = 0
            vattotals[item_taxcode]["TAXAMOUNT"] = 0
        vattotals[item_taxcode]["NETTAMOUNT"] += flt(item.base_net_amount, 2)
        vattotals[item_taxcode]["TAXAMOUNT"] += flt(
            item.base_net_amount * ((18 / 100) if item_taxcode == 1 else 0), 2
        )

    taxes_map = {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"}

    vattotals_list = []
    for key, value in vattotals.items():
        vattotals_list.append({"VATRATE": taxes_map.get(str(key))})
        vattotals_list.append({"NETTAMOUNT": flt(value["NETTAMOUNT"], 2)})
        vattotals_list.append({"TAXAMOUNT": flt(value["TAXAMOUNT"], 2)})
    return vattotals_list


def validate_cancel(doc, method):
    if doc.vfd_rctnum:
        frappe.throw(_("This invoice cannot be canceled"))


def get_itemised_tax_breakup_html(doc):
    if not doc.taxes:
        return

    itemised_tax = get_itemised_tax_breakup_data(doc)
    get_rounded_tax_amount(itemised_tax, doc.precision("tax_amount", "taxes"))
    return itemised_tax


def get_item_inclusive_amount(item):
    if item.base_net_amount == item.base_amount:
        # this is basic rate included
        item_tax_rate = json.loads(item.item_tax_rate)
        for key, value in item_tax_rate.items():
            if not value or value == 0.00:
                return flt(item.base_amount, 2)
            return flt(item.base_amount * (1 + (value / 100)), 2)  # 118% for 18% VAT
    else:
        return flt(item.base_amount, 2)


@erpnext.allow_regional
def get_itemised_tax_breakup_data(doc):
    itemised_tax = get_itemised_tax(doc.taxes)
    return itemised_tax


def get_itemised_tax(taxes, with_tax_account=False):
    itemised_tax = {}
    for tax in taxes:
        if getattr(tax, "category", None) and tax.category == "Valuation":
            continue

        item_tax_map = (
            json.loads(tax.item_wise_tax_detail) if tax.item_wise_tax_detail else {}
        )
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

                itemised_tax[item_code][tax.description] = frappe._dict(
                    dict(tax_rate=tax_rate, tax_amount=tax_amount)
                )

                if with_tax_account:
                    itemised_tax[item_code][
                        tax.description
                    ].tax_account = tax.account_head

    return itemised_tax


def get_rounded_tax_amount(itemised_tax, precision):
    # Rounding based on tax_amount precision
    for taxes in itemised_tax.values():
        for tax_account in taxes:
            taxes[tax_account]["tax_amount"] = flt(
                taxes[tax_account]["tax_amount"], precision
            )


def before_update_after_submit(doc, method):
    return
    if doc.vfd_status == "Success":
        frappe.throw(_("Cannot change Sales Invoice after VFD Status is Success!"))


def auto_enqueue(doc, method):
    if doc.is_auto_generate_vfd == True:
        enqueue_posting_vfd_invoice(doc.name)
        frappe.msgprint(
            _("Auto generated VFD for invoice {0}".format(doc.name)), alert=True
        )
