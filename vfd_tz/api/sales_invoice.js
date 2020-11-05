frappe.ui.form.on("Sales Invoice", {
    onload: function(frm) {
        frm.trigger("make_vfd_btn")
    },
    refresh: function(frm) {
        frm.trigger("make_vfd_btn")
    },
    make_vfd_btn: function(frm){
        if (frm.doc.docstatus == 1 && !frm.doc.vfd_posting_info){
            frm.add_custom_button(__('Generate VFD'),
                    
            function() {
                frappe.call({
                    method: "vfd_tz.api.sales_invoice.posting_vfd_invoice",
                    args: {
                        invoice_name: frm.doc.name,
                    },
                }); 
            });               
        }
    },
})