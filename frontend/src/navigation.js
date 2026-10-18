export const navigation = [
	{ label: "Dashboard", items: [["/", "Home"]] },
	{
		label: "Import Management",
		items: [["/import-files", "Vehicle Import Files", "Vehicle Import File"]],
	},
	{
		label: "Purchasing",
		items: [
			["/suppliers", "Suppliers", "Supplier"],
			["/purchase-orders", "Purchase Orders", "Purchase Order"],
			["/purchase-receipts", "Purchase Receipts", "Purchase Receipt"],
			["/purchase-invoices", "Purchase Invoices", "Purchase Invoice"],
			["/supplier-payments", "Supplier Payments", "Payment Entry"],
			["/landed-costs", "Landed Cost Vouchers", "Landed Cost Voucher"],
		],
	},
	{
		label: "Vehicles",
		items: [
			["/vehicles", "Vehicle Master", "Vehicle Master"],
			["/inspections", "Vehicle Inspections", "Quality Inspection"],
		],
	},
	{
		label: "Sales",
		items: [
			["/customers", "Customers", "Customer"],
			["/quotations", "Quotations", "Quotation"],
			["/sales-orders", "Sales Orders", "Sales Order"],
			["/sales-invoices", "Sales Invoices", "Sales Invoice"],
			["/customer-payments", "Customer Payments", "Payment Entry"],
		],
	},
];
export function recordLocation(record) {
	if (
		record.doctype === "Payment Entry" &&
		record.payment_type === "Pay" &&
		record.party_type === "Supplier"
	) {
		return { to: `/supplier-payments/${encodeURIComponent(record.name)}` };
	}
	const base = {
		"Vehicle Master": "/vehicles",
		"Vehicle Import File": "/import-files",
		"Purchase Order": "/purchase-orders",
		"Purchase Invoice": "/purchase-invoices",
		"Purchase Receipt": "/purchase-receipts",
		"Landed Cost Voucher": "/landed-costs",
		Customer: "/customers",
		Supplier: "/suppliers",
	}[record.doctype];
	return base
		? { to: `${base}/${encodeURIComponent(record.name)}` }
		: {
				href: `/app/${record.doctype.toLowerCase().replaceAll(" ", "-")}/${encodeURIComponent(record.name)}`,
			};
}
