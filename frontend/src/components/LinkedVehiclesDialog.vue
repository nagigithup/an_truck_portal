<script setup>
import { inject, onBeforeUnmount, ref, watch } from "vue";
import { call, __ } from "../api";
const props = defineProps({ template: String });
const { ctx } = inject("portal");
const dialog = ref(null), result = ref(null), error = ref(""), search = ref(""), status = ref(""), page = ref(1), loading = ref(false);
let timer, generation = 0;
async function load() {
	const request = ++generation;
	loading.value = true; error.value = "";
	try {
		const data = await call("an_truck_portal.api.specifications.get_linked_vehicles", {
			template: props.template, company: ctx.company, search: search.value, status: status.value, page: page.value,
		});
		if (request === generation) result.value = data;
	} catch (e) { if (request === generation) error.value = e.message; }
	finally { if (request === generation) loading.value = false; }
}
function open() { search.value = ""; status.value = ""; page.value = 1; result.value = null; dialog.value.showModal(); load(); }
watch([search, status], () => { page.value = 1; clearTimeout(timer); timer = setTimeout(load, 250); });
onBeforeUnmount(() => { clearTimeout(timer); generation++; });
defineExpose({ open });
</script>
<template>
	<dialog ref="dialog" class="operation-dialog wide-dialog" :aria-label="__('Linked Vehicles')">
		<div class="dialog-head"><h2>{{ __("Linked Vehicles") }}</h2><button type="button" class="icon" :aria-label="__('Close')" @click="dialog.close()">×</button></div>
		<div class="dialog-body">
			<div class="form-grid"><label><span>{{ __("Search by VIN, color or engine serial number") }}</span><input v-model="search" /></label><label><span>{{ __("Vehicle Status") }}</span><select v-model="status"><option value="">{{ __("All statuses") }}</option><option v-for="value in result?.statuses || []" :key="value" :value="value">{{ __(value) }}</option></select></label></div>
			<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
			<p v-if="loading" role="status">{{ __("Loading…") }}</p>
			<div v-else-if="result" class="table-wrap"><table><thead><tr><th>{{ __("VIN / Chassis Number") }}</th><th>{{ __("Color") }}</th><th>{{ __("Vehicle Status") }}</th><th>{{ __("Engine Serial Number") }}</th><th>{{ __("Receipt Date") }}</th><th>{{ __("Company") }}</th><th>{{ __("Actions") }}</th></tr></thead><tbody><tr v-if="!result.rows.length"><td colspan="7" class="empty">{{ __("No linked vehicles found.") }}</td></tr><tr v-for="row in result.rows" :key="row.name"><td><bdi>{{ row.vin }}</bdi></td><td>{{ row.color || '—' }}</td><td>{{ __(row.vehicle_status) }}</td><td><bdi>{{ row.engine_number || '—' }}</bdi></td><td>{{ row.receipt_date || '—' }}</td><td>{{ row.company }}</td><td><router-link class="text-button" :to="{ name: 'detail', params: { resource: 'vehicles', name: row.name } }" @click="dialog.close()">{{ __("View Vehicle") }}</router-link></td></tr></tbody></table></div>
		</div>
		<div class="dialog-actions"><span v-if="result">{{ __("Number of Vehicles") }}: {{ result.total }} · {{ __("Page") }} {{ page }}</span><button class="button secondary" :disabled="loading || page <= 1" @click="page--; load()">{{ __("Previous") }}</button><button class="button secondary" :disabled="loading || !result?.has_more" @click="page++; load()">{{ __("Next") }}</button><button class="button secondary" @click="dialog.close()">{{ __("Close") }}</button></div>
	</dialog>
</template>
