frappe.ui.form.on("Customer", {
    vfd_custidtype: function(frm) {
        if (frm.doc.vfd_custidtype == "1- TIN") {
            frm.set_value("vfd_custid", frm.doc.tax_id)
        }
    },
    vfd_custid: function(frm) {
        frappe.msgprint(string(frm.doc.vfd_custid.length))
        frappe.msgprint(frm.doc.vfd_custidtype.startsWith('1'))
        if (frm.doc.vfd_custid.length != 9 && frm.doc.vfd_custidtype.startsWith('1')){
            frappe.throw(__("TIN Number is should be 9 numbers only"));
        }
    },
    tax_id: function(frm) {
        frm.fields_dict.tax_id.$input.focusout(function() {
            if (frm.doc.tax_id.length != 9){
                frappe.throw(__("TIN Number is should be 9 numbers only"));
            }
            if (frm.doc.tax_id) {
                frm.set_value("vfd_custid", frm.doc.tax_id);
                frm.set_value("vfd_custidtype", "1- TIN");
            }
        });
    },
})