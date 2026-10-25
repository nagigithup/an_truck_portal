<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import WarrantyProviderDialog from "../components/WarrantyProviderDialog.vue";

const props = defineProps({ resource: String });
const { ctx } = inject("portal");
const state = ref("loading");
const error = ref("");
const rows = ref([]);
const search = ref("");
const status = ref("");
const provider = ref("");
const expiryFrom = ref("");
const expiryTo = ref("");
const page = ref(1);
const hasMore = ref(false);
const providerDialog = ref(null);

const masterTitles = {
	providers: "Warranty Providers",
	"provider-branches": "Provider Branches",
	"provider-contracts": "Provider Contracts",
	"coverage-templates": "Coverage Templates",
	"coverage-categories": "Coverage Categories",
};
const title = computed(() =>
	props.resource === "warranties"
		? "Vehicle Warranties"
		: props.resource === "warranty-claims"
			? "Warranty Claims"
			: masterTitles[props.resource],
);
const isWarranty = computed(() => props.resource === "warranties");
const isClaim = computed(() => props.resource === "warranty-claims");
const isMaster = computed(() => !isWarranty.value && !isClaim.value);
const isProviderMaster = computed(() => props.resource === "providers");
const columns = computed(() => {
	if (isWarranty.value)
		return [
			"vin",
			"vehicle_master",
			"customer_name",
			"provider_name",
			"provider_branch",
			"warranty_start_date",
			"warranty_expiry_date",
			"mileage_limit",
			"status",
		];
	if (isClaim.value)
		return [
			"name",
			"vin",
			"vehicle_master",
			"vehicle_warranty",
			"customer_name",
			"provider_name",
			"branch_name",
			"claim_date",
			"status",
			"coverage_decision",
		];
	if (!rows.value.length) return [];
	return Object.keys(rows.value[0]).filter((key) => !["modified", "can_write"].includes(key));
});

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		let result;
		if (isWarranty.value)
			result = await call("an_truck_portal.api.warranty.list_warranties", {
				search: search.value,
				status: status.value,
				provider: provider.value,
				expiry_from: expiryFrom.value,
				expiry_to: expiryTo.value,
				company: ctx.company,
				page: page.value,
			});
		else if (isClaim.value)
			result = await call("an_truck_portal.api.warranty.list_claims", {
				search: search.value,
				status: status.value,
				provider: provider.value,
				company: ctx.company,
				page: page.value,
			});
		else
			result = await call("an_truck_portal.api.warranty.list_master", {
				resource: props.resource,
				search: search.value,
				page: page.value,
			});
		rows.value = result.rows || [];
		hasMore.value = Boolean(result.has_more);
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}
onMounted(load);
watch(
	() => props.resource,
	() => {
		page.value = 1;
		search.value = "";
		status.value = "";
		provider.value = "";
		load();
	},
);
let timer;
watch([search, status, provider, expiryFrom, expiryTo], () => {
	clearTimeout(timer);
	page.value = 1;
	timer = setTimeout(load, 300);
});

function openPath(row) {
	if (isWarranty.value) return `/warranties/${encodeURIComponent(row.name)}`;
	if (isClaim.value) return `/warranty-claims/${encodeURIComponent(row.name)}`;
	return `/warranty/${props.resource}/${encodeURIComponent(row.name)}`;
}
function label(key) {
	return __(
		{
			customer_name: "Customer",
			provider_name: "Provider",
			branch_name: "Provider Branch",
			provider_branch: "Provider Branch",
			vehicle_master: "Vehicle",
			vehicle_warranty: "Warranty",
			warranty_start_date: "Start Date",
			warranty_expiry_date: "Expiry Date",
			mileage_limit: "Mileage Limit",
			claim_date: "Claim Date",
			coverage_decision: "Coverage Decision",
		}[key] || key.replaceAll("_", " "),
	);
}
function display(value, key) {
	if (value === null || value === undefined || value === "") return "—";
	if (["active", "auto_renewal", "is_extension"].includes(key))
		return value ? __("Yes") : __("No");
	return ["status", "coverage_decision"].includes(key) ? __(String(value)) : value;
}
async function changePage(delta) {
	page.value += delta;
	await load();
}
function openProvider(name = "") {
	providerDialog.value?.open(name);
}
async function providerSaved() {
	page.value = 1;
	await load();
}
</script>

<template>
	<div class="page warranty-page">
		<header class="page-head">
			<div>
				<p class="eyebrow">{{ __("Warranty") }}</p>
				<h1>{{ __(title) }}</h1>
			</div>
			<button
				v-if="isProviderMaster && ctx.permissions['Warranty Provider']?.create"
				type="button"
				class="button"
				@click="openProvider()"
			>
				+ {{ __("New Provider") }}
			</button>
		</header>
		<section class="panel">
			<div class="filter-bar">
				<div class="form-field warranty-search">
					<label for="warranty-search">{{ __("Search") }}</label
					><input
						id="warranty-search"
						v-model="search"
						:placeholder="
							isWarranty
								? __('Search VIN, vehicle or customer…')
								: isClaim
									? __('Search claim, VIN or warranty…')
									: __('Search…')
						"
					/>
				</div>
				<div v-if="!isMaster" class="form-field">
					<label for="warranty-status">{{ __("Status") }}</label
					><select id="warranty-status" v-model="status">
						<option value="">{{ __("All") }}</option>
						<template v-if="isWarranty"
							><option
								v-for="item in ['Draft', 'Active', 'Expired', 'Cancelled']"
								:key="item"
							>
								{{ item }}
							</option></template
						><template v-else
							><option
								v-for="item in [
									'Draft',
									'Submitted by Provider',
									'Under Internal Review',
									'Need More Information',
									'Approved',
									'Partially Approved',
									'Rejected',
									'Repair In Progress',
									'Repair Completed',
									'Final Documents Submitted',
									'Closed',
								]"
								:key="item"
							>
								{{ item }}
							</option></template
						>
					</select>
				</div>
				<div v-if="!isMaster" class="form-field">
					<label for="warranty-provider">{{ __("Provider") }}</label
					><input
						id="warranty-provider"
						v-model="provider"
						:placeholder="__('Provider')"
					/>
				</div>
				<div v-if="isWarranty" class="form-field">
					<label for="expiry-from">{{ __("Expiry From") }}</label
					><input id="expiry-from" v-model="expiryFrom" type="date" />
				</div>
				<div v-if="isWarranty" class="form-field">
					<label for="expiry-to">{{ __("Expiry To") }}</label
					><input id="expiry-to" v-model="expiryTo" type="date" />
				</div>
			</div>
			<div v-if="state === 'loading'" class="empty">{{ __("Loading…") }}</div>
			<div v-else-if="state === 'error'" class="empty error">{{ error }}</div>
			<div v-else-if="!rows.length" class="empty">{{ __("No records found") }}</div>
			<div v-else class="table-wrap">
				<table>
					<thead>
						<tr>
							<th v-for="key in columns" :key="key">{{ label(key) }}</th>
							<th v-if="isProviderMaster">{{ __("Actions") }}</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in rows" :key="row.name">
							<td v-for="(key, index) in columns" :key="key">
								<router-link
									v-if="index === 0"
									class="record-link"
									:to="openPath(row)"
									><bdi>{{ display(row[key], key) }}</bdi></router-link
								><span
									v-else
									:class="{
										badge: key === 'status',
										success: key === 'status' && row[key] === 'Active',
										'ltr-value': ['vin', 'phone', 'email'].includes(key),
									}"
									>{{ display(row[key], key) }}</span
								>
							</td>
							<td v-if="isProviderMaster">
								<button
									v-if="row.can_write"
									type="button"
									class="text-button"
									@click="openProvider(row.name)"
								>
									{{ __("Edit") }}</button
								><span v-else>—</span>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div v-if="state === 'ready'" class="pagination">
				<button class="button secondary" :disabled="page <= 1" @click="changePage(-1)">
					{{ __("Previous") }}</button
				><span>{{ __("Page") }} {{ page }}</span
				><button class="button secondary" :disabled="!hasMore" @click="changePage(1)">
					{{ __("Next") }}
				</button>
			</div>
		</section>
		<WarrantyProviderDialog ref="providerDialog" @saved="providerSaved" />
	</div>
</template>
