frappe.ui.form.on("Customer", {
    vfd_custidtype: function(frm) {
        if (frm.doc.vfd_custidtype == "1- TIN") {
            frm.set_value("vfd_custid", frm.doc.tax_id)
        }
    },
})