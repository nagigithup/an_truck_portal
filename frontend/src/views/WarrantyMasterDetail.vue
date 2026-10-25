<script setup>
import { onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import WarrantyProviderBranchDialog from "../components/WarrantyProviderBranchDialog.vue";
import WarrantyProviderDialog from "../components/WarrantyProviderDialog.vue";

const props = defineProps({ resource: String, name: String });
const state = ref("loading");
const error = ref("");
const data = ref(null);
const branchDialog = ref(null);
const providerDialog = ref(null);

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		data.value = await call("an_truck_portal.api.warranty.get_master", {
			resource: props.resource,
			name: props.name,
		});
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}

onMounted(load);
watch(() => [props.resource, props.name], load);

function value(row) {
	if (row.value === null || row.value === undefined || row.value === "") return "—";
	if (row.fieldtype === "Check") return row.value ? __("Yes") : __("No");
	return row.value;
}

function openBranch(name = "", edit = false) {
	branchDialog.value?.open(props.name, name, edit);
}

function openProvider() {
	providerDialog.value?.open(props.name);
}
</script>

<template>
	<div class="page warranty-page">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error">{{ error }}</div>
		<template v-else>
			<header class="panel workspace-header">
				<div>
					<p class="eyebrow">{{ __(data.doctype) }}</p>
					<h1><bdi>{{ data.name }}</bdi></h1>
				</div>
				<div class="page-actions">
					<button
						v-if="resource === 'providers' && data.can_write"
						type="button"
						class="button"
						@click="openProvider"
					>
						{{ __("Edit Provider") }}
					</button>
					<router-link class="button secondary" :to="`/warranty/${resource}`">
						{{ __("Back") }}
					</router-link>
				</div>
			</header>

			<section class="panel section-card">
				<div class="detail">
					<template v-for="field in data.fields" :key="field.fieldname">
						<div v-if="field.fieldtype !== 'Table'">
							<small>{{ __(field.label) }}</small>
							<b class="long-text">{{ value(field) }}</b>
						</div>
					</template>
				</div>
			</section>

			<section v-if="resource === 'providers'" class="panel section-card">
				<div class="section-head">
					<h2>{{ __("Branches") }}</h2>
					<div class="branch-section-actions">
						<span class="badge neutral">{{ data.branches.length }}</span>
						<button
							v-if="data.can_create_branch"
							type="button"
							class="button small"
							@click="openBranch()"
						>
							{{ __("Add Branch") }}
						</button>
					</div>
				</div>
				<div v-if="data.branches.length" class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>{{ __("Branch Name") }}</th>
								<th>{{ __("City") }}</th>
								<th>{{ __("Contact Person") }}</th>
								<th>{{ __("Mobile") }}</th>
								<th>{{ __("Email") }}</th>
								<th>{{ __("Actions") }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="branch in data.branches" :key="branch.name">
								<td><bdi>{{ branch.branch_name }}</bdi></td>
								<td>{{ branch.city || "—" }}</td>
								<td>{{ branch.contact_person || "—" }}</td>
								<td><bdi>{{ branch.mobile || "—" }}</bdi></td>
								<td><bdi>{{ branch.email || "—" }}</bdi></td>
								<td>
									<div class="branch-row-actions">
										<button type="button" class="text-button" @click="openBranch(branch.name)">
											{{ __("View") }}
										</button>
										<button
											v-if="branch.can_write"
											type="button"
											class="text-button"
											@click="openBranch(branch.name, true)"
										>
											{{ __("Edit") }}
										</button>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<div v-else class="empty">{{ __("No branches found.") }}</div>
			</section>

			<section
				v-for="field in data.fields.filter((row) => row.fieldtype === 'Table')"
				:key="field.fieldname"
				class="panel section-card"
			>
				<div class="section-head">
					<h2>{{ __(field.label) }}</h2>
					<span class="badge neutral">{{ field.value.length }}</span>
				</div>
				<div v-if="field.value.length" class="table-wrap">
					<table>
						<thead>
							<tr>
								<th v-for="key in Object.keys(field.value[0])" :key="key">
									{{ __(key.replaceAll("_", " ")) }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="(row, index) in field.value" :key="index">
								<td
									v-for="key in Object.keys(field.value[0])"
									:key="key"
									class="wrap-cell"
								>
									{{ row[key] ?? "—" }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<div v-else class="empty">{{ __("No records found") }}</div>
			</section>
		</template>

		<WarrantyProviderBranchDialog ref="branchDialog" @saved="load" />
		<WarrantyProviderDialog ref="providerDialog" @saved="load" />
	</div>
</template>
