<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { call } from "../api";
import { __ } from "../i18n";
import AppButton from "../components/AppButton.vue";
import AppCard from "../components/AppCard.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import LoadingState from "../components/LoadingState.vue";
import PageHeader from "../components/PageHeader.vue";
import SearchInput from "../components/SearchInput.vue";
import SparePartItemDialog from "../components/SparePartItemDialog.vue";
import SparePartPricingDialog from "../components/SparePartPricingDialog.vue";
import StatusBadge from "../components/StatusBadge.vue";

const { ctx } = inject("portal");
const rows = ref([]);
const search = ref("");
const page = ref(1);
const hasMore = ref(false);
const state = ref("loading");
const error = ref("");
const itemDialog = ref(null);
const pricingDialog = ref(null);
const columns = computed(() => [
	{ key: "item_code", label: __("Item Code"), ltr: true },
	{ key: "item_name", label: __("Item Name") },
	{ key: "item_group", label: __("Item Group") },
	{ key: "stock_uom", label: __("Stock UOM") },
	{ key: "status", label: __("Status") },
	{ key: "actions", label: __("Actions") },
]);
let timer;
let generation = 0;

async function load() {
	const request = ++generation;
	state.value = "loading";
	error.value = "";
	try {
		const result = await call("an_truck_portal.api.spare_parts.list_items", {
			search: search.value,
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

watch(search, () => {
	page.value = 1;
	clearTimeout(timer);
	timer = setTimeout(load, 250);
});
onMounted(load);
onBeforeUnmount(() => {
	clearTimeout(timer);
	generation++;
});

function move(delta) {
	page.value += delta;
	load();
}
</script>

<template>
	<div class="page">
		<PageHeader :title="__('Items')" :subtitle="__('Truck spare parts item catalog.')">
			<button
				v-if="ctx.permissions.Item?.create"
				type="button"
				class="button"
				@click="itemDialog.open()"
			>
				+ {{ __("New Item") }}
			</button>
		</PageHeader>
		<AppCard>
			<FilterBar>
				<SearchInput v-model="search" :placeholder="__('Search by part number or item name…')" />
				<AppButton v-if="search" variant="secondary" @click="search = ''">
					{{ __("Clear Filters") }}
				</AppButton>
			</FilterBar>
			<LoadingState v-if="state === 'loading'" />
			<EmptyState v-else-if="state === 'error'" :message="__(error)" error>
				<AppButton @click="load">{{ __("Retry") }}</AppButton>
			</EmptyState>
			<EmptyState v-else-if="!rows.length" :message="__('No spare parts found.')" />
			<DataTable v-else :columns="columns" :rows="rows" :caption="__('Spare Parts')">
				<template #item_code="{ row }">
					<bdi class="ltr-value">{{ row.item_code }}</bdi>
				</template>
				<template #status="{ row }"><StatusBadge :disabled="row.disabled" /></template>
				<template #actions="{ row }">
					<button type="button" class="text-button" @click="pricingDialog.open(row.name)">{{ __("Pricing") }}</button>
					<button
						v-if="row.can_write"
						type="button"
						class="text-button"
						@click="itemDialog.open(row.name)"
					>
						{{ __("Edit") }}
					</button>
				</template>
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
		<SparePartItemDialog ref="itemDialog" @saved="load" />
		<SparePartPricingDialog ref="pricingDialog" />
	</div>
</template>
