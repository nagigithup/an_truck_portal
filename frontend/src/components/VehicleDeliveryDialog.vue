<script setup>
import { computed, inject, ref } from "vue";
import { call, __ } from "../api";
import ConfirmDialog from "./ConfirmDialog.vue";

const props = defineProps({
	sourceDoctype: { type: String, required: true },
	sourceName: { type: String, required: true },
});
const emit = defineEmits(["confirmed"]);
const { notification } = inject("portal");
const dialog = ref(null);
const confirmDialog = ref(null);
const busy = ref(false);
const error = ref("");
const source = ref(null);
const form = ref({});
const creationResult = ref(null);
const operationKey = ref("");

const accessoryOptions = [
	["main_key", "Main Key"],
	["spare_key", "Spare Key"],
	["spare_tire", "Spare Tire"],
	["jack", "Jack"],
	["tool_kit", "Tool Kit"],
	["fire_extinguisher", "Fire Extinguisher"],
	["warning_triangle", "Warning Triangle"],
	["other", "Other"],
];

const selectedVehicle = computed(() =>
	(source.value?.vehicles || []).find((vehicle) => vehicle.name === form.value.vehicle_master),
);
const printRoute = computed(() =>
	creationResult.value
		? { name: "vehicle-delivery-print", params: { name: creationResult.value.name } }
		: null,
);

function key() {
	return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}

function blankAccessories() {
	return Object.fromEntries(accessoryOptions.map(([fieldname]) => [fieldname, false]));
}

async function open() {
	error.value = "";
	busy.value = false;
	source.value = null;
	creationResult.value = null;
	operationKey.value = key();
	form.value = { accessories: blankAccessories() };
	dialog.value?.showModal();
	try {
		source.value = await call("an_truck_portal.api.sales.get_vehicle_delivery_form", {
			source_doctype: props.sourceDoctype,
			source_name: props.sourceName,
		});
		form.value = {
			vehicle_master:
				source.value.vehicles.length === 1 ? source.value.vehicles[0].name : "",
			delivery_date: source.value.delivery_date,
			accessories: blankAccessories(),
			other_description: "",
			notes: "",
			customer_representative_name: "",
			representative_id: "",
			delivery_employee_name: source.value.delivery_employee || "",
		};
	} catch (e) {
		error.value = e?.message || __("Unable to load vehicle delivery details.");
	}
}

function close() {
	if (!busy.value) dialog.value?.close();
}

async function save() {
	if (busy.value || !source.value || creationResult.value) return;
	if (!form.value.vehicle_master) {
		error.value = __("Select a vehicle to deliver.");
		return;
	}
	if (!form.value.delivery_date) {
		error.value = __("Delivery Date is required.");
		return;
	}
	if (!(await confirmDialog.value?.ask())) return;
	busy.value = true;
	error.value = "";
	try {
		creationResult.value = await call(
			"an_truck_portal.api.sales.confirm_vehicle_delivery",
			{
				source_doctype: props.sourceDoctype,
				source_name: props.sourceName,
				data: form.value,
				idempotency_key: operationKey.value,
			},
			true,
		);
		notification.value = __("Vehicle delivery confirmed successfully: {0}", [
			creationResult.value.name,
		]);
		emit("confirmed", creationResult.value);
	} catch (e) {
		error.value = e?.message || __("Unable to confirm vehicle delivery.");
	} finally {
		busy.value = false;
	}
}

defineExpose({ open });
</script>

<template>
	<dialog
		ref="dialog"
		class="operation-dialog wide-dialog"
		:aria-label="__('Vehicle Delivery')"
		@cancel.prevent="close"
	>
		<form @submit.prevent="save">
			<div class="dialog-head">
				<div>
					<p class="eyebrow">{{ __("Sales") }}</p>
					<h2>{{ __("Vehicle Delivery") }}</h2>
				</div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body">
				<div v-if="!source && !error" class="empty compact">{{ __("Loading…") }}</div>
				<template v-if="source">
					<div class="form-grid">
						<label class="wide">
							<span>{{ __("Vehicle") }}</span>
							<select
								v-if="source.vehicles.length > 1"
								v-model="form.vehicle_master"
								required
								:disabled="!!creationResult"
							>
								<option value="">{{ __("Select") }}</option>
								<option v-for="vehicle in source.vehicles" :key="vehicle.name" :value="vehicle.name">
									{{ vehicle.chassis_number || vehicle.vin }} · {{ vehicle.item_name }}
								</option>
							</select>
							<input v-else :value="selectedVehicle?.chassis_number || selectedVehicle?.vin" disabled />
						</label>
						<label><span>{{ __("Customer Name") }}</span><input :value="source.customer_name" disabled /></label>
						<label><span>{{ __(source.source_doctype) }}</span><input :value="source.source_name" disabled /></label>
						<label><span>{{ __("Delivery Date") }}</span><input v-model="form.delivery_date" type="date" required :disabled="!!creationResult" /></label>
						<label><span>{{ __("Vehicle Type / Model") }}</span><input :value="[selectedVehicle?.vehicle_type, selectedVehicle?.model].filter(Boolean).join(' / ')" disabled /></label>
						<label><span>{{ __("VIN / Chassis Number") }}</span><input :value="selectedVehicle?.chassis_number || selectedVehicle?.vin" disabled /></label>
						<label><span>{{ __("Plate Number") }}</span><input :value="selectedVehicle?.plate_number || ''" disabled /></label>
						<label class="wide"><span>{{ __("Vehicle Description") }}</span><textarea :value="selectedVehicle?.description || ''" disabled></textarea></label>
					</div>

					<div class="dialog-section-head"><h3>{{ __("Delivered Accessories") }}</h3></div>
					<div class="delivery-accessories">
						<label v-for="([fieldname, label]) in accessoryOptions" :key="fieldname">
							<input v-model="form.accessories[fieldname]" type="checkbox" :disabled="!!creationResult" />
							<span>{{ __(label) }}</span>
						</label>
					</div>
					<label v-if="form.accessories.other" class="delivery-other">
						<span>{{ __("Other Description") }}</span>
						<input v-model="form.other_description" :disabled="!!creationResult" />
					</label>

					<div class="dialog-section-head"><h3>{{ __("Delivery Information") }}</h3></div>
					<div class="form-grid">
						<label class="wide"><span>{{ __("Notes") }}</span><textarea v-model="form.notes" :disabled="!!creationResult"></textarea></label>
						<label><span>{{ __("Customer Representative Name") }}</span><input v-model="form.customer_representative_name" :disabled="!!creationResult" /></label>
						<label><span>{{ __("Representative ID / Iqama Number") }}</span><input v-model="form.representative_id" :disabled="!!creationResult" /></label>
						<label class="wide"><span>{{ __("Delivery Employee Name") }}</span><input v-model="form.delivery_employee_name" :disabled="!!creationResult" /></label>
					</div>
					<p v-if="creationResult" class="notice success-notice" role="status">
						{{ __("Vehicle delivery confirmed successfully: {0}", [creationResult.name]) }}
					</p>
				</template>
				<p v-if="error" class="form-error" role="alert">{{ error }}</p>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="busy" @click="close">
					{{ creationResult ? __("Close") : __("Cancel") }}
				</button>
				<router-link v-if="printRoute" class="button" :to="printRoute" target="_blank">
					{{ __("View / Print Delivery Note") }}
				</router-link>
				<button v-else class="button" :disabled="busy || !source">
					{{ busy ? __("Processing...") : __("Confirm Delivery") }}
				</button>
			</div>
		</form>
	</dialog>
	<ConfirmDialog
		ref="confirmDialog"
		title="Confirm Vehicle Delivery"
		message="This will submit the Delivery Note and mark the selected vehicle as delivered. Continue?"
		cancel-label="Cancel"
		confirm-label="Confirm Delivery"
	/>
</template>

<style scoped>
.delivery-accessories {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 8px;
}
.delivery-accessories label {
	display: flex;
	align-items: center;
	gap: 8px;
	min-height: 42px;
	padding: 8px 10px;
	border: 1px solid var(--line);
	border-radius: var(--radius);
	background: var(--paper);
}
.delivery-accessories input {
	width: auto;
	min-height: auto;
}
.delivery-other {
	display: grid;
	gap: 5px;
	margin-top: 10px;
}
.delivery-other span {
	font-size: 11px;
	font-weight: 600;
	color: var(--muted);
}
@media (max-width: 760px) {
	.delivery-accessories {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
</style>
