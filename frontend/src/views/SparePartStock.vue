<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { call } from "../api";
import { __, language } from "../i18n";
import AppButton from "../components/AppButton.vue";
import AppCard from "../components/AppCard.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import LoadingState from "../components/LoadingState.vue";
import PageHeader from "../components/PageHeader.vue";
import SearchInput from "../components/SearchInput.vue";

const { ctx } = inject("portal");
const rows = ref([]);
const warehouses = ref([]);
const warehouse = ref("");
const search = ref("");
const page = ref(1);
const hasMore = ref(false);
const state = ref("loading");
const error = ref("");
const columns = computed(() => [
	{ key: "item_code", label: __("Item Code"), ltr: true },
	{ key: "item_name", label: __("Item Name") },
	{ key: "warehouse", label: __("Warehouse") },
	{ key: "actual_qty", label: __("Actual Quantity"), ltr: true },
	{ key: "reserved_qty", label: __("Reserved Quantity"), ltr: true },
	{ key: "available_qty", label: __("Available Quantity"), ltr: true },
]);
let timer;
let generation = 0;

function quantity(value) {
	return new Intl.NumberFormat(language.value, { maximumFractionDigits: 6 }).format(value || 0);
}

async function load() {
	const request = ++generation;
	state.value = "loading";
	error.value = "";
	try {
		const result = await call("an_truck_portal.api.spare_parts.list_stock", {
			search: search.value,
			company: ctx.company,
			warehouse: warehouse.value,
			page: page.value,
		});
		if (request !== generation) return;
		rows.value = result.rows;
		hasMore.value = result.has_more;
		state.value = "ready";
	} catch (e) {
		if (request !== generation) return;
		error.value = e.message;
		state.value = "error";
	}
}

async function initialize() {
	state.value = "loading";
	try {
		const result = await call("an_truck_portal.api.spare_parts.get_stock_options", {
			company: ctx.company,
		});
		warehouses.value = result.warehouses;
		await load();
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}

watch([search, warehouse], () => {
	page.value = 1;
	clearTimeout(timer);
	timer = setTimeout(load, 250);
});
onMounted(initialize);
onBeforeUnmount(() => {
	clearTimeout(timer);
	generation++;
});

function clearFilters() {
	search.value = "";
	warehouse.value = "";
}

function move(delta) {
	page.value += delta;
	load();
}
</script>

<template>
	<div class="page">
		<PageHeader :title="__('Stock')" :subtitle="__('Current spare parts stock balances. Read only.')" />
		<AppCard>
			<FilterBar>
				<SearchInput v-model="search" :placeholder="__('Search by part number or item name…')" />
				<FormField
					v-model="warehouse"
					:label="__('Warehouse')"
					type="select"
					:options="warehouses"
				/>
				<AppButton variant="secondary" @click="clearFilters">{{ __("Clear Filters") }}</AppButton>
			</FilterBar>
			<LoadingState v-if="state === 'loading'" />
			<EmptyState v-else-if="state === 'error'" :message="__(error)" error>
				<AppButton @click="initialize">{{ __("Retry") }}</AppButton>
			</EmptyState>
			<EmptyState v-else-if="!rows.length" :message="__('No stock balances found.')" />
			<DataTable v-else :columns="columns" :rows="rows" :caption="__('Spare Parts Stock')">
				<template #item_code="{ row }"><bdi class="ltr-value">{{ row.item_code }}</bdi></template>
				<template #actual_qty="{ row }"><bdi class="ltr-value">{{ quantity(row.actual_qty) }}</bdi></template>
				<template #reserved_qty="{ row }"><bdi class="ltr-value">{{ quantity(row.reserved_qty) }}</bdi></template>
				<template #available_qty="{ row }"><bdi class="ltr-value">{{ quantity(row.available_qty) }}</bdi></template>
			</DataTable>
			<div class="pagination">
				<span>{{ __("Page") }} <bdi>{{ page }}</bdi></span>
				<div class="row-actions">
					<AppButton variant="secondary" :disabled="page === 1 || state === 'loading'" @click="move(-1)">
						{{ __("Previous") }}
					</AppButton>
					<AppButton variant="secondary" :disabled="!hasMore || state === 'loading'" @click="move(1)">
						{{ __("Next") }}
					</AppButton>
				</div>
			</div>
		</AppCard>
	</div>
</template>
