<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({ name: String, paymentKind: { type: String, default: "supplier" } });
const state = ref("loading");
const error = ref("");
const result = ref(null);
const payment = computed(() => result.value?.payment || {});
const isCustomer = computed(() => props.paymentKind === "customer");
const deskUrl = computed(
	() => `/app/payment-entry/${encodeURIComponent(payment.value.name || props.name)}`,
);

function amount(value, currency = payment.value.paid_from_currency) {
	if (value == null || value === "") return "—";
	try {
		return new Intl.NumberFormat(document.documentElement.lang, {
			style: "currency",
			currency: currency || "SAR",
			maximumFractionDigits: 2,
		}).format(Number(value));
	} catch {
		return `${Number(value).toLocaleString()} ${currency || ""}`;
	}
}

function date(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat(document.documentElement.lang, { dateStyle: "medium" }).format(
		new Date(String(value).replace(" ", "T")),
	);
}

function documentStatus(row) {
	return row.docstatus === 2
		? __("Cancelled")
		: row.docstatus === 1
			? __(row.status || "Submitted")
			: __(row.status || "Draft");
}

function referenceRoute(reference) {
	if (reference.doctype === "Purchase Invoice") {
		return { name: "purchase-invoice-detail", params: { name: reference.document } };
	}
	if (reference.doctype === "Purchase Order") {
		return { name: "purchase-order-detail", params: { name: reference.document } };
	}
	if (reference.doctype === "Sales Invoice") {
		return { name: "sales-invoice-detail", params: { name: reference.document } };
	}
	if (reference.doctype === "Sales Order") {
		return { name: "sales-order-detail", params: { name: reference.document } };
	}
	return null;
}

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		result.value = await call(isCustomer.value ? "an_truck_portal.api.sales.get_customer_payment" : "an_truck_portal.api.import_file.get_supplier_payment", {
			payment_entry: props.name,
		});
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}

onMounted(load);
watch(() => props.name, load);
</script>

<template>
	<div class="page supplier-payment-detail">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error" role="alert">{{ error }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div>
					<p class="eyebrow">{{ __(isCustomer ? "Customer Payment Details" : "Supplier Payment Details") }}</p>
					<h1><bdi>{{ payment.name }}</bdi></h1>
					<div class="page-actions detail-actions">
						<router-link class="button secondary small" :to="isCustomer ? '/customer-payments' : '/supplier-payments'">
							{{ __(isCustomer ? "Back to Customer Payments" : "Back to Supplier Payments") }}
						</router-link>
						<router-link
							v-if="payment.vehicle_import_file"
							:to="{ name: 'import-workspace', params: { name: payment.vehicle_import_file } }"
						>
							{{ __("Vehicle Import File") }}: <bdi>{{ payment.vehicle_import_file }}</bdi>
						</router-link>
						<a class="button secondary small" :href="deskUrl" target="_blank" rel="noopener">
							{{ __("Open in Desk") }}
						</a>
					</div>
				</div>
				<div class="workspace-metrics">
					<div><small>{{ __("Status") }}</small><span class="badge neutral">{{ documentStatus(payment) }}</span></div>
					<div><small>{{ __(isCustomer ? "Customer" : "Supplier") }}</small><b>{{ isCustomer ? payment.customer_name || payment.customer : payment.supplier_name || payment.supplier }}</b></div>
					<div><small>{{ __("Company") }}</small><b>{{ payment.company }}</b></div>
					<div><small>{{ __("Payment Date") }}</small><b>{{ date(payment.posting_date) }}</b></div>
					<div><small>{{ __("Paid Amount") }}</small><b>{{ amount(payment.paid_amount) }}</b></div>
					<div><small>{{ __("Payment Method") }}</small><b>{{ payment.payment_method || "—" }}</b></div>
				</div>
			</header>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Payment Details") }}</h2></div>
				<div class="compact-details">
					<div><small>{{ __("Paid From") }}</small><b><bdi>{{ payment.paid_from || "—" }}</bdi></b></div>
					<div><small>{{ __("Paid To") }}</small><b><bdi>{{ payment.paid_to || "—" }}</bdi></b></div>
					<div><small>{{ __("Paid From Currency") }}</small><b>{{ payment.paid_from_currency || "—" }}</b></div>
					<div><small>{{ __("Paid To Currency") }}</small><b>{{ payment.paid_to_currency || "—" }}</b></div>
					<div><small>{{ __("Received Amount") }}</small><b>{{ amount(payment.received_amount, payment.paid_to_currency) }}</b></div>
					<div><small>{{ __("Reference No") }}</small><b><bdi>{{ payment.reference_no || "—" }}</bdi></b></div>
					<div><small>{{ __("Reference Date") }}</small><b>{{ date(payment.reference_date) }}</b></div>
				</div>
			</section>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("References") }}</h2><span class="badge neutral">{{ result.references.length }}</span></div>
				<div v-if="result.references.length" class="table-wrap"><table>
					<thead><tr><th>{{ __("Reference Type") }}</th><th>{{ __("Reference Document") }}</th><th>{{ __("Total Amount") }}</th><th>{{ __("Outstanding Amount") }}</th><th>{{ __("Allocated Amount") }}</th><th>{{ __("Exchange Rate") }}</th></tr></thead>
					<tbody><tr v-for="reference in result.references" :key="reference.name">
						<td>{{ __(reference.doctype) }}</td>
						<td><router-link v-if="referenceRoute(reference)" :to="referenceRoute(reference)"><bdi>{{ reference.document }}</bdi></router-link><bdi v-else>{{ reference.document }}</bdi></td>
						<td>{{ amount(reference.total_amount, payment.paid_to_currency) }}</td><td>{{ amount(reference.outstanding_amount, payment.paid_to_currency) }}</td><td>{{ amount(reference.allocated_amount, payment.paid_to_currency) }}</td><td>{{ reference.exchange_rate ?? "—" }}</td>
					</tr></tbody>
				</table></div>
				<div v-else class="empty compact">{{ __("No references found.") }}</div>
			</section>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Attachments") }}</h2></div>
				<div v-if="result.attachments.length" class="document-list"><div v-for="file in result.attachments" :key="file.name">
					<span>{{ __("Attachment") }}</span><bdi>{{ file.file_name }}</bdi>
					<span class="attachment-links"><a :href="file.file_url" target="_blank" rel="noopener">{{ __("View") }}</a><a :href="file.file_url" download>{{ __("Download") }}</a></span>
				</div></div>
				<div v-else class="empty compact">{{ __("No attachments have been added.") }}</div>
			</section>
			<p v-if="payment.remarks" class="panel section-card detail-notes"><strong>{{ __("Notes") }}:</strong> {{ payment.remarks }}</p>
		</template>
	</div>
</template>
