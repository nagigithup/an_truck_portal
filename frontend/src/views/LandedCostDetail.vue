<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({ name: String });
const state = ref("loading");
const error = ref("");
const result = ref(null);
const voucher = computed(() => result.value?.voucher || {});
const deskUrl = computed(
	() => `/app/landed-cost-voucher/${encodeURIComponent(voucher.value.name || props.name)}`,
);

function amount(value, currency = voucher.value.company_currency || "SAR") {
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

function receiptRoute(row) {
	return row.doctype === "Purchase Receipt"
		? { name: "purchase-receipt-detail", params: { name: row.document } }
		: null;
}

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		result.value = await call("an_truck_portal.api.import_file.get_landed_cost_voucher", {
			landed_cost_voucher: props.name,
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
	<div class="page landed-cost-detail">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error" role="alert">{{ error }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div>
					<p class="eyebrow">{{ __("Landed Cost Details") }}</p>
					<h1><bdi>{{ voucher.name }}</bdi></h1>
					<div class="page-actions detail-actions">
						<router-link class="button secondary small" to="/landed-costs">{{ __("Back to Landed Costs") }}</router-link>
						<router-link v-if="voucher.vehicle_import_file" :to="{ name: 'import-workspace', params: { name: voucher.vehicle_import_file } }">
							{{ __("Vehicle Import File") }}: <bdi>{{ voucher.vehicle_import_file }}</bdi>
						</router-link>
						<a class="button secondary small" :href="deskUrl" target="_blank" rel="noopener">{{ __("Open in Desk") }}</a>
					</div>
				</div>
				<div class="workspace-metrics">
					<div><small>{{ __("Status") }}</small><span class="badge neutral">{{ __(voucher.status) }}</span></div>
					<div><small>{{ __("Company") }}</small><b>{{ voucher.company }}</b></div>
					<div><small>{{ __("Posting Date") }}</small><b>{{ date(voucher.posting_date) }}</b></div>
					<div><small>{{ __("Allocation Method") }}</small><b>{{ __(voucher.allocation_method) }}</b></div>
					<div><small>{{ __("Total Additional Costs") }}</small><b>{{ amount(voucher.total_taxes_and_charges) }}</b></div>
					<div><small>{{ __("Additional Cost Rows") }}</small><b>{{ result.costs.length }}</b></div>
				</div>
			</header>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Linked Purchase Receipts") }}</h2><span class="badge neutral">{{ result.purchase_receipts.length }}</span></div>
				<div v-if="result.purchase_receipts.length" class="table-wrap"><table>
					<thead><tr><th>{{ __("Receipt Document") }}</th><th>{{ __("Supplier") }}</th><th>{{ __("Posting Date") }}</th><th>{{ __("Grand Total") }}</th></tr></thead>
					<tbody><tr v-for="receipt in result.purchase_receipts" :key="receipt.name">
						<td><router-link v-if="receiptRoute(receipt)" :to="receiptRoute(receipt)"><bdi>{{ receipt.document }}</bdi></router-link><bdi v-else>{{ receipt.document }}</bdi></td><td>{{ receipt.supplier || "—" }}</td><td>{{ date(receipt.posting_date) }}</td><td>{{ amount(receipt.grand_total, receipt.currency) }}</td>
					</tr></tbody>
				</table></div>
				<div v-else class="empty compact">{{ __("No linked Purchase Receipts.") }}</div>
			</section>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Additional Cost Rows") }}</h2><span class="badge neutral">{{ result.costs.length }}</span></div>
				<div v-if="result.costs.length" class="table-wrap"><table>
					<thead><tr><th>{{ __("Expense Type") }}</th><th>{{ __("Expense Account") }}</th><th>{{ __("Amount") }}</th><th>{{ __("Amount (Company Currency)") }}</th><th>{{ __("Exchange Rate") }}</th><th>{{ __("Attachments") }}</th></tr></thead>
					<tbody><tr v-for="cost in result.costs" :key="cost.name">
						<td>{{ cost.description || "—" }}</td><td><bdi>{{ cost.expense_account || "—" }}</bdi></td><td>{{ amount(cost.amount, cost.account_currency) }}</td><td>{{ amount(cost.base_amount) }}</td><td>{{ cost.exchange_rate ?? "—" }}</td>
						<td><span v-if="cost.attachments.length" class="attachment-links"><span v-for="file in cost.attachments" :key="file.name"><a :href="file.file_url" target="_blank" rel="noopener">{{ __("View") }}: {{ file.file_name }}</a><a :href="file.file_url" download>{{ __("Download") }}</a></span></span><span v-else>—</span></td>
					</tr></tbody>
				</table></div>
				<div v-else class="empty compact">{{ __("No additional costs found.") }}</div>
			</section>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Allocated Vehicle Costs") }}</h2><span class="badge neutral">{{ result.allocations.length }}</span></div>
				<div v-if="result.allocations.length" class="table-wrap"><table>
					<thead><tr><th>{{ __("Item") }}</th><th>{{ __("Description") }}</th><th>{{ __("Receipt Document") }}</th><th>{{ __("Quantity") }}</th><th>{{ __("Rate") }}</th><th>{{ __("Original Amount") }}</th><th>{{ __("Allocated Cost") }}</th><th>{{ __("Total Landed Cost") }}</th></tr></thead>
					<tbody><tr v-for="item in result.allocations" :key="item.name">
						<td><bdi>{{ item.item_code }}</bdi></td><td>{{ item.description || "—" }}</td><td><router-link v-if="item.receipt_document_type === 'Purchase Receipt'" :to="{ name: 'purchase-receipt-detail', params: { name: item.receipt_document } }"><bdi>{{ item.receipt_document }}</bdi></router-link><bdi v-else>{{ item.receipt_document }}</bdi></td><td>{{ item.qty }}</td><td>{{ amount(item.rate) }}</td><td>{{ amount(item.amount) }}</td><td>{{ amount(item.allocated_cost) }}</td><td>{{ amount(Number(item.amount || 0) + Number(item.allocated_cost || 0)) }}</td>
					</tr></tbody>
				</table></div>
				<div v-else class="empty compact">{{ __("No allocated vehicle costs found.") }}</div>
			</section>

			<section class="panel section-card">
				<div class="section-head"><h2>{{ __("Attachments") }}</h2></div>
				<div v-if="result.attachments.length" class="document-list"><div v-for="file in result.attachments" :key="file.name">
					<span>{{ __("Attachment") }}</span><bdi>{{ file.file_name }}</bdi><span class="attachment-links"><a :href="file.file_url" target="_blank" rel="noopener">{{ __("View") }}</a><a :href="file.file_url" download>{{ __("Download") }}</a></span>
				</div></div>
				<div v-else class="empty compact">{{ __("No attachments have been added.") }}</div>
			</section>
		</template>
	</div>
</template>
