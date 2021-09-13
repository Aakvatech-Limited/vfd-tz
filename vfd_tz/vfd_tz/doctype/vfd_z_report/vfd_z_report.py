# Copyright (c) 2021, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate
from vfd_tz.api.sales_invoice import get_item_taxcode


class VFDZReport(Document):
    def validate(self):
        self.set_data()

    def before_submit(self):
        pass

    def on_submit(self):
        pass

    def set_data(self):
        company = frappe.get_value("VFD Registration", self.vfd_registration, "company")
        z_last_gc = get_z_last_gc(self.vfd_registration)
        self.vfd_gc_previous = z_last_gc
        self.znumber = str(nowdate()).replace("-", "")
        invoices = get_invoices(company, z_last_gc)
        if len(invoices) > 0:
            self.vfd_gc_from = z_last_gc + 1
            self.vfd_gc_to = get_invoices_last_gc(company, z_last_gc)
            self.set_invoices(invoices)
            self.dailytotalamount = get_gross_between(
                company, self.vfd_gc_from, self.vfd_gc_to
            )
            self.set_vat_totals()
        else:
            self.vfd_gc_from = None
            self.vfd_gc_to = None
        # self.gross = get_gross(company)
        self.gross = get_gross_between(company, 1, self.vfd_gc_to or z_last_gc)
        for invoice in self.invoices:
            self.discounts += invoice.discount_amount
        self.ticketsfiscal = len(self.invoices)
        canceled_invoices = self.get_canceled_invoices()
        self.ticketsvoid = self.ticketsnonfiscal = len(canceled_invoices)
        self.ticketsvoidtotal = sum(
            invoice["base_rounded_total"] or invoice["base_grand_total"]
            for invoice in canceled_invoices
        )
        self.set_payments()

    def get_canceled_invoices(self):
        company, report_start_date = frappe.get_value(
            "VFD Registration",
            self.vfd_registration,
            ["company", "vfd_z_report_start_date"],
        )
        canceled_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 2,
                "company": company,
                "vfd_z_report": ["in", [None, "", self.name]],
                "posting_date": [">=", report_start_date],
            },
            fields=["name", "base_rounded_total", "base_grand_total", "vfd_z_report"],
        )
        for invoice in canceled_invoices:
            if not invoice.vfd_z_report:
                frappe.db.set_value(
                    "Sales Invoice", invoice.name, "vfd_z_report", self.name
                )
        return canceled_invoices

    def set_payments(self):
        total_payments = 0
        self.payments = []
        payments_list = frappe.get_all(
            "Sales Invoice Payment",
            filters={"parent": ["in", [invoice.invoice for invoice in self.invoices]]},
            fields=["sum(base_amount) as amount", "mode_of_payment"],
            group_by="mode_of_payment",
        )
        payments_data = {}
        for payment in payments_list:
            total_payments += payment.amount
            vfd_pmttype = frappe.get_value(
                "Mode of Payment", payment.mode_of_payment, "vfd_pmttype"
            )
            if not payments_data.get(vfd_pmttype):
                payments_data.setdefault(vfd_pmttype, payment.amount)
            else:
                payments_data[vfd_pmttype] += payment.amount
        for key, value in payments_data.items():
            row = self.append("payments", {})
            row.pmttype = key
            row.pmtamount = value
        diff_total = self.dailytotalamount - total_payments
        if diff_total > 0:
            row = self.append("payments", {})
            row.pmttype = "INVOICE"
            row.pmtamount = diff_total

    def set_invoices(self, invoices):
        self.invoices = []
        if len(invoices) == 0:
            return
        for el in invoices:
            row = self.append("invoices", {})
            row.invoice = el.name
            row.vfd_gc = el.vfd_gc
            row.total_taxes_and_charges = el.base_total_taxes_and_charges
            row.base_net_total = el.base_net_total
            row.base_grand_total = el.base_rounded_total or el.base_grand_total
            row.discount_amount = el.base_discount_amount

    def set_vat_totals(self):
        self.vats = []
        invoices_list = []
        for row in self.invoices:
            invoices_list.append(row.invoice)
        if not invoices_list:
            return
        items = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": ["in", invoices_list]},
            fields=["*"],
        )
        vattotals = get_vattotals(items)
        for el in vattotals:
            row = self.append("vats", {})
            row.nettamount = el.get("nettamount")
            row.taxamount = el.get("taxamount")
            row.vatrate = el.get("vatrate")


def get_vattotals(items):
    vattotals = {}
    for item in items:
        item_taxcode = get_item_taxcode(
            item.item_tax_template, item.item_code, item.parent
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
        vattotals_list.append(
            {
                "vatrate": taxes_map.get(str(key)),
                "nettamount": flt(value["NETTAMOUNT"], 2),
                "taxamount": flt(value["TAXAMOUNT"], 2),
            }
        )

    return vattotals_list


def get_z_last_gc(vfd_registration):
    report_list = frappe.db.sql(
        """
    SELECT MAX(vfd_gc_to) as to_gc
    FROM `tabVFD Z Report`
    WHERE 
        vfd_registration = '{0}'
        and docstatus = 1
    """.format(
            vfd_registration
        ),
        as_dict=True,
    )
    if len(report_list) > 0 and report_list[0].get("to_gc"):
        return report_list[0].get("to_gc")
    else:
        return 0


def get_invoices_last_gc(company, last_gc):
    invoices_list = frappe.db.sql(
        """
    SELECT MAX(vfd_gc) as gc
    FROM `tabSales Invoice`
    WHERE 
        company = '{0}'
        and docstatus = 1
        and vfd_gc > {1}
    """.format(
            company, last_gc
        ),
        as_dict=True,
    )
    if len(invoices_list) > 0 and invoices_list[0].get("gc"):
        return invoices_list[0].get("gc")
    else:
        return None


def get_invoices(company, last_gc):
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"company": company, "docstatus": 1, "vfd_gc": [">", last_gc]},
        fields=["*"],
        order_by="vfd_gc",
    )
    return invoices


# def get_gross(company):
#     invoices_list = frappe.db.sql(
#         """
#     SELECT SUM(IF(base_rounded_total > 0, base_rounded_total, base_grand_total)) as total
#     FROM `tabSales Invoice`
#     WHERE
#         company = '{0}'
#         and docstatus = 1
#         and vfd_gc > 0
#     """.format(
#             company
#         ),
#         as_dict=True,
#     )
#     return invoices_list[0].get("total")


def get_gross_between(company, start, end):
    invoices_list = frappe.db.sql(
        """
    SELECT SUM(IF(base_rounded_total > 0, base_rounded_total, base_grand_total)) as total
    FROM `tabSales Invoice`
    WHERE 
        company = '{0}'
        and docstatus = 1
        and vfd_gc BETWEEN {1} AND {2}
    """.format(
            company, start, end
        ),
        as_dict=True,
    )
    return invoices_list[0].get("total")
