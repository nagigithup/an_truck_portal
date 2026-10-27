<script setup>
import { inject, ref } from "vue";
import { call, __ } from "../api";
const props = defineProps({ center: String });
const emit = defineEmits(["created"]);
const { ctx, notification } = inject("portal");
const dialog = ref(null), source = ref(null), name = ref(""), parent = ref(""), busy = ref(false), error = ref("");
async function open() { error.value = ""; parent.value = ""; dialog.value?.showModal(); try { source.value = await call("an_truck_portal.api.maintenance_centers.get_warehouse_setup_options", { center: props.center, company: ctx.company }); name.value = source.value.warehouse_name; } catch (e) { error.value = e.message; } }
function close() { if (!busy.value) dialog.value?.close(); }
async function save() { busy.value = true; try { const result = await call("an_truck_portal.api.maintenance_centers.create_warehouse", { center: props.center, company: ctx.company, warehouse_name: name.value, parent_warehouse: parent.value }, true); dialog.value?.close(); notification.value = __("Center warehouse created successfully."); emit("created", result); } catch (e) { error.value = e.message; } finally { busy.value = false; } }
defineExpose({ open });
</script>
<template><dialog ref="dialog" class="operation-dialog" :aria-label="__('Create Center Warehouse')" @cancel.prevent="close"><form @submit.prevent="save"><div class="dialog-head"><div><p class="eyebrow">{{ __("Maintenance Center") }}</p><h2>{{ __("Create Center Warehouse") }}</h2></div><button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button></div><div class="dialog-body"><div class="form-grid create-import-grid"><label><span>{{ __("Warehouse Name") }}</span><input v-model="name" required /></label><label><span>{{ __("Parent Warehouse") }}</span><select v-model="parent" required><option value="">{{ __("Select") }}</option><option v-for="row in source?.parent_warehouses || []" :key="row.value" :value="row.value">{{ row.label }}</option></select></label></div><p class="notice compact">{{ __("This action creates a standard ERPNext warehouse for this center and company.") }}</p><p v-if="error" class="form-error">{{ __(error) }}</p></div><div class="dialog-actions"><button type="button" class="button secondary" :disabled="busy" @click="close">{{ __("Cancel") }}</button><button class="button" :disabled="busy">{{ __(busy ? 'Processing...' : 'Create Warehouse') }}</button></div></form></dialog></template>
