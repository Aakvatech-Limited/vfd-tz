# Copyright (c) 2013, Aakvatech and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import pandas as pd


def execute(filters=None):
    # frappe.msgprint(str(filters))
    columns = get_columns()
    data = []

    # Get Invoice List in the si_entries
    si_entries = get_sales_invoice_entries(filters)
    # frappe.msgprint("si entries are: " + str(si_entries))

    # below is to try overcome issue of not getting column names in pivot_table
    if si_entries:
        colnames = [key for key in si_entries[0].keys()]
        # frappe.msgprint("colnames are: " + str(colnames))
        df = pd.DataFrame.from_records(si_entries, columns=colnames)
        # frappe.msgprint("dataframe columns are is: " + str(df.columns.tolist()))
        pvt = pd.pivot_table(
            df,
            values="net_amount",
            index=[
				"vfd_rctvnum",
                "vfd_date",
                "invoice_no",
                "customer_name",
                "tax_id",
                #"customer_group",
                #"territory",
            ],
            columns="item_tax_template",
            fill_value=0
        )
        # frappe.msgprint(str(pvt))
        #
        data = pvt.reset_index().values.tolist()
        # frappe.msgprint("Data is: " + str(data))

        for column_name in pvt.columns.values.tolist():
            # frappe.msgprint("Column is: " + str(column_name))
            columns += [
                {
                    "label": _(column_name),
                    "fieldtype": "Currency",
                    "precision": 2,
                    "width": 150,
                }
            ]
    return columns, data


def get_columns():
    columns = [
        {"label": _("VFD Number"), "fieldname": "vfd_rctvnum", "width": 100},
        {"label": _("VFD Date"),"fieldname": "vfd_date","fieldtype": "Date","width": 110},
        {"label": _("Invoice No"), "fieldname": "invoice_no", "fieldtype": "Link/Sales Invoice","width": 180},
        {"label": _("Customer Name"), "fieldname": "customer_name", "width": 250},
        {"label": _("Cust. Tin No"), "fieldname": "tax_id", "width": 110},
        #{"label": _("Customer Group"), "fieldname": "customer_group", "width": 150},
        #{"label": _("Territory"), "fieldname": "territory", "width": 110},
    ]
    return columns


def get_sales_invoice_entries(filters):
    return frappe.db.sql(
        """SELECT 	vfd_rctvnum,
					si.vfd_status,
					si.name as invoice_no,
					si.vfd_date,
					si.customer_name,
					si.customer_group, 
					si.territory,
					if(si.tax_id is null, '999999999', si.tax_id) as tax_id,
					sii.item_tax_template,
					sum(sii.base_net_amount) as net_amount
			FROM `tabSales Invoice` si 
				INNER JOIN `tabSales Invoice Item` sii ON si.name = sii.parent
			WHERE (si.posting_date >= %(from_date)s 
					and si.posting_date <= %(to_date)s) 
					and si.is_return = 0
					and si.docstatus = 1
					and si.vfd_rctvnum is not null
			GROUP BY si.name
			ORDER BY vfd_rctvnum""",
        filters,
        as_dict=1,
    )
