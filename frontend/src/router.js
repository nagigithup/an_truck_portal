import { createRouter, createWebHistory } from "vue-router";
import Dashboard from "./views/Dashboard.vue";
import Records from "./views/Records.vue";
import Detail from "./views/Detail.vue";
import ImportWorkspace from "./views/ImportWorkspace.vue";
import Parties from "./views/Parties.vue";
import PartyForm from "./views/PartyForm.vue";
import PurchaseOrderDetail from "./views/PurchaseOrderDetail.vue";
import PurchaseInvoiceDetail from "./views/PurchaseInvoiceDetail.vue";
import PurchaseReceiptDetail from "./views/PurchaseReceiptDetail.vue";
import SupplierPaymentDetail from "./views/SupplierPaymentDetail.vue";
import LandedCostDetail from "./views/LandedCostDetail.vue";
import SalesDocumentDetail from "./views/SalesDocumentDetail.vue";
import VehicleDeliveryPrint from "./views/VehicleDeliveryPrint.vue";
import WarrantyDashboard from "./views/WarrantyDashboard.vue";
import WarrantyRecords from "./views/WarrantyRecords.vue";
import WarrantyDetail from "./views/WarrantyDetail.vue";
import WarrantyClaimDetail from "./views/WarrantyClaimDetail.vue";
import WarrantyMasterDetail from "./views/WarrantyMasterDetail.vue";

const routes = [
	{ path: "/", name: "home", component: Dashboard, meta: { title: "Home" } },
	{ path: "/:resource(customers|suppliers)", name: "parties", component: Parties, props: true },
	{ path: "/:resource(customers|suppliers)/new", redirect: (to) => `/${to.params.resource}` },
	{
		path: "/:resource(customers|suppliers)/:name",
		name: "party-detail",
		component: PartyForm,
		props: true,
	},
	{
		path: "/:resource(import-files|vehicles|purchase-orders|purchase-receipts|purchase-invoices|supplier-payments|landed-costs|quotations|sales-orders|sales-invoices|customer-payments|serials|inspections)",
		name: "records",
		component: Records,
		props: true,
	},
	{
		path: "/import-files/:name",
		name: "import-workspace",
		component: ImportWorkspace,
		props: true,
	},
	{
		path: "/purchase-orders/:name",
		name: "purchase-order-detail",
		component: PurchaseOrderDetail,
		props: true,
	},
	{
		path: "/purchase-invoices/:name",
		name: "purchase-invoice-detail",
		component: PurchaseInvoiceDetail,
		props: true,
	},
	{
		path: "/purchase-receipts/:name",
		name: "purchase-receipt-detail",
		component: PurchaseReceiptDetail,
		props: true,
	},
	{
		path: "/supplier-payments/:name",
		name: "supplier-payment-detail",
		component: SupplierPaymentDetail,
		props: true,
	},
	{
		path: "/landed-costs/:name",
		name: "landed-cost-detail",
		component: LandedCostDetail,
		props: true,
	},
	{
		path: "/quotations/:name",
		name: "quotation-detail",
		component: SalesDocumentDetail,
		props: (route) => ({ name: route.params.name, doctype: "Quotation" }),
	},
	{
		path: "/sales-orders/:name",
		name: "sales-order-detail",
		component: SalesDocumentDetail,
		props: (route) => ({ name: route.params.name, doctype: "Sales Order" }),
	},
	{
		path: "/sales-invoices/:name",
		name: "sales-invoice-detail",
		component: SalesDocumentDetail,
		props: (route) => ({ name: route.params.name, doctype: "Sales Invoice" }),
	},
	{
		path: "/delivery-notes/:name/print",
		name: "vehicle-delivery-print",
		component: VehicleDeliveryPrint,
		props: true,
	},
	{
		path: "/customer-payments/:name",
		name: "customer-payment-detail",
		component: SupplierPaymentDetail,
		props: (route) => ({ name: route.params.name, paymentKind: "customer" }),
	},
	{ path: "/warranty-dashboard", name: "warranty-dashboard", component: WarrantyDashboard },
	{ path: "/warranties", name: "warranties", component: WarrantyRecords, props: { resource: "warranties" } },
	{ path: "/warranties/:name", name: "warranty-detail", component: WarrantyDetail, props: true },
	{ path: "/warranty-claims", name: "warranty-claims", component: WarrantyRecords, props: { resource: "warranty-claims" } },
	{ path: "/warranty-claims/:name", name: "warranty-claim-detail", component: WarrantyClaimDetail, props: true },
	{ path: "/warranty/:resource(providers|provider-branches|provider-contracts|coverage-templates|coverage-categories)", name: "warranty-master", component: WarrantyRecords, props: true },
	{ path: "/warranty/:resource(providers|provider-branches|provider-contracts|coverage-templates|coverage-categories)/:name", name: "warranty-master-detail", component: WarrantyMasterDetail, props: true },
	{
		path: "/:resource(vehicles)/:name",
		name: "detail",
		component: Detail,
		props: true,
	},
	{ path: "/:pathMatch(.*)*", redirect: "/" },
];
export const router = createRouter({
	history: createWebHistory("/an-truck-portal"),
	routes,
	scrollBehavior: () => ({ top: 0 }),
});
