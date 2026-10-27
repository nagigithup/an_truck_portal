<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import CenterSalesReturnDialog from "../components/CenterSalesReturnDialog.vue";
import MaintenanceCenterDialog from "../components/MaintenanceCenterDialog.vue";
import SparePartsSalesDialog from "../components/SparePartsSalesDialog.vue";
import SupplierPaymentDialog from "../components/SupplierPaymentDialog.vue";

const props = defineProps({ name: String });
const { ctx } = inject("portal");
const state = ref("loading"), error = ref(""), result = ref(null), tab = ref("invoices");
const editDialog = ref(null), salesDialog = ref(null), paymentDialog = ref(null), returnDialog = ref(null);
const tabs = computed(() => [
	{ key: "invoices", label: __("Invoices") },
	{ key: "payments", label: __("Allocated Payments") },
	{ key: "credit_notes", label: __("Credit Notes") },
	{ key: "account", label: __("Statement of Account") },
]);
function amount(value, currency = "") { return `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${currency}`; }
async function load() {
	state.value = "loading"; error.value = "";
	try { result.value = await call("an_truck_portal.api.maintenance_centers.get_center", { name: props.name, company: ctx.company }); state.value = "ready"; }
	catch (e) { error.value = e.message; state.value = "error"; }
}
onMounted(load);
watch(() => props.name, load);
</script>

<template>
	<div class="page center-detail">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error">{{ __(error) }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div><p class="eyebrow">{{ __("Maintenance Center") }}</p><h1>{{ result.center.center_name }}</h1><p>{{ result.center.contact_person }} · <bdi>{{ result.center.mobile || result.center.email }}</bdi></p><small>{{ result.center.customer || __("Sales Customer not linked") }}</small></div>
				<div class="page-actions">
					<button class="button secondary small" @click="editDialog.open(name)">{{ __("Sales Profile") }}</button>
					<button v-if="result.center.customer" class="button small" @click="salesDialog.open({ sale_type: 'center', center: name })">{{ __("Sell to Center") }}</button>
					<button v-if="result.center.customer" class="button small" @click="paymentDialog.open()">{{ __("Record Payment") }}</button>
					<button class="button secondary small" @click="tab = 'account'">{{ __("Statement of Account") }}</button>
					<button v-if="result.center.customer" class="button secondary small" @click="returnDialog.open()">{{ __("Sales Return") }}</button>
				</div>
			</header>
			<div v-for="summary in result.summaries.length ? result.summaries : [result.summary]" :key="summary.currency" class="compact-details spare-sale-totals panel">
				<div><small>{{ __("Invoice Total") }}</small><b>{{ amount(summary.invoiced, summary.currency) }}</b></div>
				<div><small>{{ __("Credit Notes") }}</small><b>{{ amount(summary.credit_notes, summary.currency) }}</b></div>
				<div><small>{{ __("Allocated Payments") }}</small><b>{{ amount(summary.allocated_payments, summary.currency) }}</b></div>
				<div><small>{{ __("Outstanding Amount") }}</small><b>{{ amount(summary.outstanding, summary.currency) }}</b></div>
			</div>
			<div class="panel center-tabs" role="tablist"><button v-for="item in tabs" :key="item.key" :class="{ active: tab === item.key }" role="tab" @click="tab = item.key">{{ item.label }}</button></div>
			<section class="panel section-card">
				<div v-if="tab === 'invoices'" class="table-wrap"><table><thead><tr><th>{{ __("Sales Invoice") }}</th><th>{{ __("Posting Date") }}</th><th>{{ __("Price List") }}</th><th>{{ __("Net Total") }}</th><th>{{ __("Taxes") }}</th><th>{{ __("Invoice Total") }}</th><th>{{ __("Allocated Payments") }}</th><th>{{ __("Outstanding Amount") }}</th><th>{{ __("Status") }}</th><th>{{ __("Actions") }}</th></tr></thead><tbody><tr v-for="row in result.invoices" :key="row.name"><td><router-link class="record-link" :to="{ name: 'spare-parts-sale-detail', params: { name: row.name } }">{{ row.name }}</router-link></td><td>{{ row.posting_date }}</td><td>{{ row.selling_price_list }}</td><td>{{ amount(row.net_total, row.currency) }}</td><td>{{ amount(row.total_taxes_and_charges, row.currency) }}</td><td>{{ amount(row.grand_total, row.currency) }}</td><td>{{ amount(row.allocated_payments, row.currency) }}</td><td>{{ amount(row.outstanding_amount, row.currency) }}</td><td>{{ __(row.docstatus === 0 ? "Draft" : row.status) }}</td><td><button v-if="row.docstatus === 1 && row.outstanding_amount > 0" class="text-button" @click="paymentDialog.open(row.name)">{{ __("Record Payment") }}</button><button v-if="row.docstatus === 1" class="text-button" @click="returnDialog.open(row.name)">{{ __("Sales Return") }}</button></td></tr></tbody></table><div v-if="!result.invoices.length" class="empty">{{ __("No center sales found.") }}</div></div>

				<div v-else-if="tab === 'payments'" class="table-wrap"><p class="notice compact">{{ __("Payments are allocated to outstanding invoices and are not restricted to the invoice or collection month.") }}</p><table><thead><tr><th>{{ __("Payment Entry") }}</th><th>{{ __("Posting Date") }}</th><th>{{ __("Allocated Amount") }}</th><th>{{ __("Status") }}</th></tr></thead><tbody><tr v-for="row in result.payments" :key="row.name"><td><router-link class="record-link" :to="{ name: 'customer-payment-detail', params: { name: row.name } }">{{ row.name }}</router-link></td><td>{{ row.posting_date }}</td><td>{{ amount(row.allocated_amount, row.currency) }}</td><td>{{ __(row.status) }}</td></tr></tbody></table><div v-if="!result.payments.length" class="empty">{{ __("No center payments found.") }}</div></div>

				<div v-else-if="tab === 'credit_notes'" class="table-wrap"><table><thead><tr><th>{{ __("Credit Note") }}</th><th>{{ __("Return Against") }}</th><th>{{ __("Posting Date") }}</th><th>{{ __("Net Total") }}</th><th>{{ __("Taxes") }}</th><th>{{ __("Credit Amount") }}</th><th>{{ __("Outstanding Amount") }}</th><th>{{ __("Status") }}</th></tr></thead><tbody><tr v-for="row in result.credit_notes" :key="row.name"><td><router-link class="record-link" :to="{ name: 'spare-parts-sale-detail', params: { name: row.name } }">{{ row.name }}</router-link></td><td><router-link class="record-link" :to="{ name: 'spare-parts-sale-detail', params: { name: row.return_against } }">{{ row.return_against }}</router-link></td><td>{{ row.posting_date }}</td><td>{{ amount(Math.abs(row.net_total), row.currency) }}</td><td>{{ amount(Math.abs(row.total_taxes_and_charges), row.currency) }}</td><td>{{ amount(Math.abs(row.grand_total), row.currency) }}</td><td>{{ amount(row.outstanding_amount, row.currency) }}</td><td>{{ __(row.docstatus === 0 ? "Draft" : row.status) }}</td></tr></tbody></table><div v-if="!result.credit_notes.length" class="empty">{{ __("No credit notes found.") }}</div></div>

				<div v-else class="table-wrap"><p class="notice compact">{{ __("This monthly view reports standard invoices, credit notes, collections, and current outstanding balances. It does not create invoices or stock movements.") }}</p><table><thead><tr><th>{{ __("Month") }}</th><th>{{ __("Invoice Total") }}</th><th>{{ __("Credit Notes") }}</th><th>{{ __("Allocated Payments") }}</th><th>{{ __("Current Outstanding") }}</th></tr></thead><tbody><tr v-for="row in result.monthly_accounts" :key="`${row.month}-${row.currency}`"><td><bdi>{{ row.month }}</bdi></td><td>{{ amount(row.invoice_total, row.currency) }}</td><td>{{ amount(row.credit_notes, row.currency) }}</td><td>{{ amount(row.allocated_payments, row.currency) }}</td><td>{{ amount(row.outstanding, row.currency) }}</td></tr></tbody></table><div v-if="!result.monthly_accounts.length" class="empty">{{ __("No account activity found.") }}</div></div>
			</section>
			<MaintenanceCenterDialog ref="editDialog" @saved="load" />
			<SparePartsSalesDialog ref="salesDialog" @created="load" />
			<SupplierPaymentDialog ref="paymentDialog" :customer="result.center.customer || ''" :allowed-invoices="result.invoices.filter((row) => row.docstatus === 1 && row.outstanding_amount > 0).map((row) => row.name)" @created="load" />
			<CenterSalesReturnDialog ref="returnDialog" :center="name" @created="load" />
		</template>
	</div>
</template>
