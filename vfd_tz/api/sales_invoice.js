frappe.ui.form.on("Sales Invoice", {
    onload: function(frm) {
        frm.trigger("make_vfd_btn")
        console.log("VFD")
    },
    refresh: function(frm) {
        // frm.trigger("make_vfd_btn")
        console.log("VFD")
    },
    make_vfd_btn: function(frm){
        // if (frm.doc.docstatus == 1 && frm.doc.enabled_auto_create_delivery_notes == 1){
            frm.add_custom_button(__('Generate VFD'),
                    
            function() {
                frappe.call({
                    method: "vfd_tz.api.sales_invoice.vfd_invoice_posting",
                    args: {
                        invoice_name: frm.doc.name,
                    },
                }); 
            });               
        // }
    },
})