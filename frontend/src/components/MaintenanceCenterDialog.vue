<script setup>
import { computed, inject, reactive, ref } from "vue";
import { call, __ } from "../api";
import FormField from "./FormField.vue";
const emit = defineEmits(["saved"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null), loading = ref(false), saving = ref(false), error = ref(""), name = ref(""), modified = ref(""), canWrite = ref(false), customers = ref([]);
const data = reactive({});
const title = computed(() => __("Center Sales Profile"));
async function open(center = "") {
	name.value = center; error.value = ""; loading.value = true; dialog.value?.showModal();
	try { const result = await call("an_truck_portal.api.maintenance_centers.get_form", { name: center, company: ctx.company }); Object.assign(data, result.record); customers.value = result.customers || []; modified.value = result.modified || ""; canWrite.value = result.can_write; }
	catch (e) { error.value = e.message; } finally { loading.value = false; }
}
function close() { if (!saving.value) dialog.value?.close(); }
async function save() {
	if (saving.value || !canWrite.value) return;
	saving.value = true;
	try { const result = await call("an_truck_portal.api.maintenance_centers.save_center", { name: name.value, modified: modified.value, company: ctx.company, data: { customer: data.customer || "" } }, true); dialog.value?.close(); notification.value = __("Center sales profile updated successfully."); emit("saved", result); }
	catch (e) { error.value = e.message; } finally { saving.value = false; }
}
defineExpose({ open });
</script>
<template><dialog ref="dialog" class="operation-dialog" :aria-label="title" @cancel.prevent="close"><form @submit.prevent="save"><div class="dialog-head"><div><p class="eyebrow">{{ __("Authorized Center") }}</p><h2>{{ title }}</h2></div><button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button></div><div class="dialog-body"><div class="form-grid create-import-grid"><FormField v-model="data.center_name" class="field-span-full" :label="__('Center Name')" disabled /><FormField v-model="data.contact_person" :label="__('Contact Person')" disabled /><FormField v-model="data.mobile" :label="__('Mobile')" type="tel" ltr disabled /><FormField v-model="data.email" :label="__('Email')" type="email" ltr disabled /><label class="wide"><span>{{ __("Sales Customer") }}</span><select v-model="data.customer" :disabled="loading || !canWrite"><option value="">{{ __("Not linked") }}</option><option v-for="row in customers" :key="row.name" :value="row.name">{{ row.customer_name || row.name }}</option></select><small>{{ __("Commercial sales use this existing Customer; warranty claims remain separate.") }}</small></label></div><p v-if="error" class="form-error" role="alert">{{ __(error) }}</p></div><div class="dialog-actions"><button type="button" class="button secondary" :disabled="saving" @click="close">{{ __(canWrite ? 'Cancel' : 'Close') }}</button><button v-if="canWrite" class="button" :disabled="saving || loading">{{ __(saving ? 'Saving…' : 'Save') }}</button></div></form></dialog></template>
