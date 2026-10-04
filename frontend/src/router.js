import { createRouter, createWebHistory } from "vue-router";
import Dashboard from "./views/Dashboard.vue";
import Records from "./views/Records.vue";
import Detail from "./views/Detail.vue";
import Parties from "./views/Parties.vue";
import PartyForm from "./views/PartyForm.vue";

const routes = [
	{ path: "/", name: "home", component: Dashboard, meta: { title: "Home" } },
	{ path: "/:resource(customers|suppliers)", name: "parties", component: Parties, props: true },
	{
		path: "/:resource(customers|suppliers)/new",
		name: "party-new",
		component: PartyForm,
		props: true,
	},
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
		path: "/:resource(import-files|vehicles)/:name",
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
