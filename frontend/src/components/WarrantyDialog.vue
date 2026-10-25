<script setup>
import { computed, inject, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({ salesInvoice: String, context: Object });
const emit = defineEmits(["created"]);
const { notification } = inject("portal");
const dialog = ref(null);
const busy = ref(false);
const error = ref("");
const form = ref({});
const configuration = ref(null);
const availableVehicles = computed(() => props.context?.can_create ? props.context.vehicles : props.context?.vehicles?.filter((row) => row.existing_warranty) || []);
const selected = computed(() => availableVehicles.value.find((row) => row.vehicle_master === form.value.vehicle_master));
const template = computed(() => props.context?.templates?.find((row) => row.name === form.value.coverage_template));

function open() {
	const row = availableVehicles.value[0];
	form.value = { vehicle_master: row?.vehicle_master || "", coverage_template: "", warranty_start_date: row?.start_date || "", warranty_provider: "", provider_contract: "", notes: "" };
	configuration.value = null; error.value = ""; dialog.value?.showModal();
}
function close() { if (!busy.value) dialog.value?.close(); }
async function configure() {
	if (!(form.value.vehicle_master && form.value.coverage_template && form.value.warranty_start_date) || selected.value?.existing_warranty) return;
	try {
		configuration.value = await call("an_truck.warranty.workflow.get_warranty_configuration", {
			vehicle_master: form.value.vehicle_master, coverage_template: form.value.coverage_template,
			start_date: form.value.warranty_start_date, provider: form.value.warranty_provider || undefined,
		});
		if (configuration.value.provider) form.value.warranty_provider = configuration.value.provider;
		if (configuration.value.contract) form.value.provider_contract = configuration.value.contract;
	} catch (e) { error.value = e.message; }
}
watch(() => form.value.vehicle_master, () => {
	form.value.warranty_start_date = selected.value?.start_date || ""; configuration.value = null; configure();
});
watch([() => form.value.coverage_template, () => form.value.warranty_start_date, () => form.value.warranty_provider], configure);
async function save() {
	if (selected.value?.existing_warranty) { dialog.value?.close(); location.href = `/app/vehicle-warranty/${encodeURIComponent(selected.value.existing_warranty)}`; return; }
	busy.value = true; error.value = "";
	try {
		const result = await call("an_truck.warranty.workflow.create_warranty_from_invoice", { sales_invoice: props.salesInvoice, ...form.value }, true);
		notification.value = __("Vehicle Warranty {0} created.", [result.name]); dialog.value?.close(); emit("created", result);
	} catch (e) { error.value = e.message; } finally { busy.value = false; }
}
defineExpose({ open });
</script>

<template>
	<dialog ref="dialog" class="operation-dialog" :aria-label="__('Add Warranty / إضافة ضمان')" @cancel.prevent="close">
		<form @submit.prevent="save">
			<div class="dialog-head"><div><p class="eyebrow">{{ __('Sales Invoice') }}</p><h2>{{ selected?.existing_warranty ? __('View Warranty') : __('Add Warranty / إضافة ضمان') }}</h2></div><button type="button" class="icon" @click="close">×</button></div>
			<div class="dialog-body">
				<div class="form-grid">
					<label class="wide"><span>{{ __('VIN / Chassis Number') }}</span><select v-if="availableVehicles.length > 1" v-model="form.vehicle_master" required><option v-for="row in availableVehicles" :key="row.vehicle_master" :value="row.vehicle_master">{{ row.vin }}</option></select><input v-else :value="selected?.vin" disabled /></label>
					<label><span>{{ __('Vehicle Summary') }}</span><input :value="selected?.vehicle?.label" disabled /></label>
					<label><span>{{ __('Customer Summary') }}</span><input :value="selected?.customer?.label" disabled /></label>
					<template v-if="!selected?.existing_warranty">
						<label class="wide"><span>{{ __('Warranty Package / Coverage Template') }}</span><select v-model="form.coverage_template" required><option value="">{{ __('Select') }}</option><option v-for="row in context.templates" :key="row.name" :value="row.name">{{ row.template_name }}</option></select></label>
						<label><span>{{ __('Start Date') }}</span><input v-model="form.warranty_start_date" type="date" required /></label>
						<label><span>{{ __('Duration') }}</span><input :value="template ? `${template.duration} ${__(template.duration_unit)}` : ''" disabled /></label>
						<label><span>{{ __('Expiry Date') }}</span><input :value="configuration?.expiry_date || ''" disabled /></label>
						<label v-if="configuration?.providers?.length > 1"><span>{{ __('Warranty Provider') }}</span><select v-model="form.warranty_provider" required><option value="">{{ __('Select') }}</option><option v-for="row in configuration.providers" :key="row">{{ row }}</option></select></label>
						<label v-if="configuration?.contracts?.length > 1"><span>{{ __('Provider Contract') }}</span><select v-model="form.provider_contract" required><option value="">{{ __('Select') }}</option><option v-for="row in configuration.contracts" :key="row.name" :value="row.name">{{ row.contract_number }}</option></select></label>
						<label class="wide"><span>{{ __('Notes') }}</span><textarea v-model="form.notes"></textarea></label>
					</template>
					<p v-else class="notice compact wide">{{ __('An applicable warranty already exists for this VIN.') }}</p>
				</div>
				<p v-if="error" class="notice error" role="alert">{{ __(error) }}</p>
			</div>
			<div class="dialog-actions"><button type="button" class="button secondary" @click="close">{{ __('Cancel') }}</button><button class="button" :disabled="busy">{{ selected?.existing_warranty ? __('View Warranty') : __('Add Warranty / إضافة ضمان') }}</button></div>
		</form>
	</dialog>
</template>
