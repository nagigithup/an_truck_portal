<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import AppButton from "../components/AppButton.vue";
import AppCard from "../components/AppCard.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import LoadingState from "../components/LoadingState.vue";
import MaintenanceCenterDialog from "../components/MaintenanceCenterDialog.vue";
import PageHeader from "../components/PageHeader.vue";
import SearchInput from "../components/SearchInput.vue";

const rows = ref([]), search = ref(""), page = ref(1), more = ref(false), state = ref("loading"), error = ref(""), dialog = ref(null);
const columns = computed(() => ["Center Name", "Contact", "Sales Customer", "Actions"].map((label) => ({ key: label.toLowerCase().replaceAll(" ", "_"), label: __(label) })));
let timer;
async function load() {
	state.value = "loading";
	try { const result = await call("an_truck_portal.api.maintenance_centers.list_centers", { search: search.value, page: page.value }); rows.value = result.rows; more.value = result.has_more; state.value = "ready"; }
	catch (e) { error.value = e.message; state.value = "error"; }
}
watch(search, () => { page.value = 1; clearTimeout(timer); timer = setTimeout(load, 250); });
onMounted(load);
</script>

<template>
	<div class="page">
		<PageHeader :title="__('Maintenance Centers')" :subtitle="__('Authorized warranty providers and branches with linked commercial sales profiles.')" />
		<AppCard>
			<FilterBar><SearchInput v-model="search" :placeholder="__('Search maintenance centers…')" /></FilterBar>
			<LoadingState v-if="state === 'loading'" />
			<EmptyState v-else-if="state === 'error'" :message="__(error)" error><AppButton @click="load">{{ __("Retry") }}</AppButton></EmptyState>
			<EmptyState v-else-if="!rows.length" :message="__('No maintenance centers found.')" />
			<DataTable v-else :columns="columns" :rows="rows" :caption="__('Maintenance Centers')">
				<template #center_name="{ row }"><router-link class="record-link" :to="{ name: 'maintenance-center-detail', params: { name: row.name } }">{{ row.customer_name }}</router-link><small>{{ __(row.center_type) }}</small></template>
				<template #contact="{ row }"><bdi>{{ row.mobile_no || row.email_id || "—" }}</bdi><small>{{ row.customer || __("Sales Customer not linked") }}</small></template>
				<template #sales_customer="{ row }">{{ row.customer || __("Sales Customer not linked") }}</template>
				<template #actions="{ row }"><router-link class="text-button" :to="{ name: 'maintenance-center-detail', params: { name: row.name } }">{{ __("View") }}</router-link><button v-if="row.can_write" class="text-button" @click="dialog.open(row.name)">{{ __("Sales Profile") }}</button></template>
			</DataTable>
			<div class="pagination"><span>{{ __("Page") }} {{ page }}</span><div class="row-actions"><AppButton variant="secondary" :disabled="page === 1" @click="page--; load()">{{ __("Previous") }}</AppButton><AppButton variant="secondary" :disabled="!more" @click="page++; load()">{{ __("Next") }}</AppButton></div></div>
		</AppCard>
		<MaintenanceCenterDialog ref="dialog" @saved="load" />
	</div>
</template>
