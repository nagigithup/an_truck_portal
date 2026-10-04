<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { call } from "../api";
import { __ } from "../i18n";
import PageHeader from "../components/PageHeader.vue";
import AppCard from "../components/AppCard.vue";
import AppButton from "../components/AppButton.vue";
import SearchInput from "../components/SearchInput.vue";
import FilterBar from "../components/FilterBar.vue";
import FormField from "../components/FormField.vue";
import DataTable from "../components/DataTable.vue";
import StatusBadge from "../components/StatusBadge.vue";
import EmptyState from "../components/EmptyState.vue";
import LoadingState from "../components/LoadingState.vue";
const props = defineProps({ resource: String });
const { ctx } = inject("portal");
const doctype = computed(() => (props.resource === "customers" ? "Customer" : "Supplier"));
const prefix = computed(() => doctype.value.toLowerCase());
const rows = ref([]),
	filters = ref({}),
	search = ref(""),
	page = ref(1),
	more = ref(false),
	state = ref("loading"),
	error = ref(""),
	metadata = ref([]);
const filterFields = computed(() =>
	metadata.value.filter((f) =>
		[prefix.value + "_group", prefix.value + "_type", "territory", "country"].includes(f.name),
	),
);
const columns = computed(() => [
	{ key: "party", label: __(doctype.value) },
	{
		key: props.resource === "customers" ? "customer_type" : "supplier_group",
		label: __(props.resource === "customers" ? "Customer Type" : "Supplier Group"),
	},
	{ key: "phone", label: __("Phone"), ltr: true },
	{ key: "tax_id", label: __("Tax ID"), ltr: true },
	{
		key: props.resource === "customers" ? "territory" : "country",
		label: __(props.resource === "customers" ? "Territory" : "Country"),
	},
	{ key: "status", label: __("Status") },
	{ key: "actions", label: __("Actions") },
]);
let timer,
	generation = 0;
async function load() {
	const request = ++generation;
	state.value = "loading";
	try {
		const data = await call("an_truck.portal_parties.list_parties", {
			doctype: doctype.value,
			company: ctx.company,
			filters: filters.value,
			search: search.value,
			page: page.value,
		});
		if (request === generation) {
			rows.value = data.rows;
			more.value = data.has_more;
			state.value = "ready";
		}
	} catch (e) {
		if (request === generation) {
			error.value = e.message;
			state.value = "error";
		}
	}
}
function applyFilters() {
	page.value = 1;
	clearTimeout(timer);
	generation++;
	timer = setTimeout(load, 250);
}
watch([search, filters], applyFilters, { deep: true });
onMounted(async () => {
	try {
		metadata.value = (
			await call("an_truck.portal_parties.get_options", {
				doctype: doctype.value,
				company: ctx.company,
			})
		).fields;
		await load();
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
});
onBeforeUnmount(() => {
	clearTimeout(timer);
	generation++;
});
function move(delta) {
	page.value += delta;
	load();
}
function location(row) {
	return `/${props.resource}/${encodeURIComponent(row.name)}`;
}
</script>
<template>
	<div class="page">
		<PageHeader
			:title="__(resource === 'customers' ? 'Customers' : 'Suppliers')"
			:subtitle="__('party.shared')"
			><router-link
				v-if="ctx.permissions[doctype]?.create"
				class="button"
				:to="`/${resource}/new`"
				>+ {{ __(`New ${doctype}`) }}</router-link
			></PageHeader
		>
		<AppCard
			><FilterBar
				><SearchInput v-model="search" /><FormField
					v-for="field in filterFields"
					:key="field.name"
					v-model="filters[field.name]"
					:label="__(field.label)"
					:type="field.type === 'Select' ? 'select' : 'text'"
					:options="
						field.type === 'Select'
							? field.options.split('\n').filter(Boolean)
							: undefined
					"
					:link="
						field.type === 'Link'
							? { doctype, field: field.name, company: ctx.company }
							: undefined
					"
				/><FormField
					v-model="filters.disabled"
					:label="__('Status')"
					type="select"
					:options="[
						{ value: '0', label: 'Active' },
						{ value: '1', label: 'Disabled' },
					]"
				/><AppButton
					variant="secondary"
					@click="
						filters = {};
						search = '';
					"
					>{{ __("Clear Filters") }}</AppButton
				></FilterBar
			>
			<LoadingState v-if="state === 'loading'" /><EmptyState
				v-else-if="state === 'error'"
				:message="__(error)"
				error
				><AppButton @click="load">{{ __("Retry") }}</AppButton></EmptyState
			>
			<EmptyState
				v-else-if="!rows.length"
				:message="
					__(resource === 'customers' ? 'No customers found.' : 'No suppliers found.')
				"
				><router-link
					v-if="ctx.permissions[doctype]?.create"
					class="button"
					:to="`/${resource}/new`"
					>{{ __(`Add ${doctype}`) }}</router-link
				></EmptyState
			>
			<DataTable
				v-else
				:columns="columns"
				:rows="rows"
				:caption="__(resource === 'customers' ? 'Customers' : 'Suppliers')"
				><template #party="{ row }"
					><router-link class="record-link" :to="location(row)">{{
						row[`${prefix}_name`]
					}}</router-link
					><small class="ltr-value">{{ row.name }}</small></template
				><template #customer_type="{ row }">{{ __(row.customer_type) }}</template
				><template #phone="{ row }"
					><span class="ltr-value">{{
						row.mobile_no || row.phone || "—"
					}}</span></template
				><template #status="{ row }"><StatusBadge :disabled="row.disabled" /></template
				><template #actions="{ row }"
					><div class="row-actions">
						<router-link class="text-button" :to="location(row)">{{
							__("View")
						}}</router-link
						><router-link
							v-if="row.can_write"
							class="text-button"
							:to="`${location(row)}?edit=1`"
							>{{ __("Edit") }}</router-link
						>
					</div></template
				></DataTable
			>
			<div class="pagination">
				<span
					>{{ __("Page") }} <bdi>{{ page }}</bdi></span
				>
				<div class="row-actions">
					<AppButton
						variant="secondary"
						:disabled="page === 1 || state === 'loading'"
						@click="move(-1)"
						>{{ __("Previous") }}</AppButton
					><AppButton
						variant="secondary"
						:disabled="!more || state === 'loading'"
						@click="move(1)"
						>{{ __("Next") }}</AppButton
					>
				</div>
			</div>
		</AppCard>
	</div>
</template>
