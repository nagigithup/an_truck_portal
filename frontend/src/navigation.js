export const navigation = [
	{
		label: "Import Management",
		hideLabel: true,
		items: [
			["/import-files", "Vehicle Import Files", "Vehicle Import File"],
			["/vehicles", "Vehicle Master", "Vehicle Master"],
		],
	},
	{
		label: "Purchasing",
		items: [
			["/suppliers", "Suppliers", "Supplier"],
			["/purchase-orders", "Purchase Orders", "Purchase Order"],
			["/purchase-receipts", "Purchase Receipts", "Purchase Receipt"],
			["/purchase-invoices", "Purchase Invoices", "Purchase Invoice"],
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
