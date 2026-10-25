<script setup>
import { onMounted, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({ name: String });
const state = ref("loading");
const error = ref("");
const data = ref(null);

async function load() {
	state.value = "loading";
	try { data.value = await call("an_truck_portal.api.warranty.get_warranty", { name: props.name }); state.value = "ready"; }
	catch (e) { error.value = e.message; state.value = "error"; }
}
onMounted(load);
watch(() => props.name, load);
function date(value) { return value ? new Intl.DateTimeFormat(document.documentElement.lang || "en", { dateStyle: "medium" }).format(new Date(`${String(value).slice(0,10)}T00:00:00`)) : "—"; }
function money(value, currency) { if (value === null || value === undefined || value === "") return "—"; try { return new Intl.NumberFormat(document.documentElement.lang || "en", { style: "currency", currency: currency || "SAR" }).format(Number(value)); } catch { return value; } }
</script>

<template>
	<div class="page warranty-page">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error">{{ error }}</div>
		<template v-else>
			<header class="panel workspace-header"><div><p class="eyebrow">{{ __("Vehicle Warranty") }}</p><h1><bdi>{{ data.warranty.vin }}</bdi></h1><p><bdi>{{ data.warranty.name }}</bdi></p></div><div class="page-actions"><router-link class="button secondary" to="/warranties">{{ __("Back to Warranties") }}</router-link><a class="button" :href="data.certificate_url" target="_blank" rel="noopener">{{ __("Warranty Certificate") }}</a></div></header>
			<section class="panel section-card"><div class="section-head"><h2>{{ __("Warranty Details") }}</h2><span :class="['badge', { success: data.warranty.status === 'Active' }]">{{ __(data.warranty.status) }}</span></div><div class="detail">
				<div><small>{{ __("VIN") }}</small><bdi><b>{{ data.warranty.vin }}</b></bdi></div><div><small>{{ __("Vehicle") }}</small><bdi><b>{{ data.warranty.vehicle_master }}</b></bdi></div><div><small>{{ __("Model") }}</small><b>{{ data.warranty.vehicle_model || '—' }}</b></div><div><small>{{ __("Customer") }}</small><b>{{ data.warranty.customer_name || data.warranty.customer }}</b></div><div><small>{{ __("Company") }}</small><b>{{ data.warranty.company }}</b></div><div><small>{{ __("Provider") }}</small><b>{{ data.warranty.provider_name || data.warranty.provider }}</b></div><div><small>{{ __("Provider Branch") }}</small><b>{{ data.warranty.provider_branch || '—' }}</b></div><div><small>{{ __("Provider Contract") }}</small><bdi><b>{{ data.warranty.provider_contract }}</b></bdi></div><div><small>{{ __("Coverage Template") }}</small><b>{{ data.warranty.coverage_template }}</b></div><div><small>{{ __("Start Date") }}</small><b>{{ date(data.warranty.start_date) }}</b></div><div><small>{{ __("Expiry Date") }}</small><b>{{ date(data.warranty.expiry_date) }}</b></div><div><small>{{ __("Activation Source") }}</small><b>{{ __(data.warranty.activation_source) }}</b></div>
			</div></section>
			<section class="panel section-card"><div class="section-head"><div><p class="eyebrow">{{ __("Immutable issued snapshot") }}</p><h2>{{ __("Coverage Snapshot") }}</h2></div><span class="badge neutral">{{ __("Read only") }}</span></div><div v-if="data.coverage.length" class="table-wrap"><table><thead><tr><th>{{ __("Covered Category") }}</th><th>{{ __("Description") }}</th><th>{{ __("Coverage") }}</th><th>{{ __("Financial Limit") }}</th><th>{{ __("Mileage Limit") }}</th><th>{{ __("Conditions") }}</th><th>{{ __("Exclusions") }}</th></tr></thead><tbody><tr v-for="row in data.coverage" :key="row.category"><td>{{ row.category }}</td><td class="wrap-cell">{{ row.description || '—' }}</td><td>{{ row.covered ? __("Covered") : __("Not Covered") }}</td><td>{{ money(row.coverage_limit, data.warranty.currency) }}</td><td>{{ row.mileage_limit || '—' }}</td><td class="wrap-cell">{{ row.conditions || '—' }}</td><td class="wrap-cell">{{ row.exclusions || '—' }}</td></tr></tbody></table></div><div v-else class="empty">{{ __("No coverage items found.") }}</div></section>
			<section class="panel section-card"><div class="section-head"><h2>{{ __("Related Claims") }}</h2><span class="badge neutral">{{ data.claims.length }}</span></div><div v-if="data.claims.length" class="table-wrap"><table><thead><tr><th>{{ __("Claim Number") }}</th><th>{{ __("Claim Date") }}</th><th>{{ __("Provider Branch") }}</th><th>{{ __("Status") }}</th><th>{{ __("Coverage Decision") }}</th></tr></thead><tbody><tr v-for="claim in data.claims" :key="claim.name"><td><router-link class="record-link" :to="`/warranty-claims/${encodeURIComponent(claim.name)}`"><bdi>{{ claim.name }}</bdi></router-link></td><td>{{ date(claim.claim_date) }}</td><td>{{ claim.provider_branch || '—' }}</td><td><span class="badge">{{ __(claim.status) }}</span></td><td>{{ __(claim.coverage_decision || 'Pending') }}</td></tr></tbody></table></div><div v-else class="empty">{{ __("No related claims.") }}</div></section>
		</template>
	</div>
</template>
