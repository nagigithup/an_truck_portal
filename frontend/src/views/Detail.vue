<script setup>
import { onMounted, ref, watch } from "vue";
import { call, __ } from "../api";
import VehicleDrawer from "../components/VehicleDrawer.vue";
import TemplateSpecifications from "../components/TemplateSpecifications.vue";
const props = defineProps({ resource: String, name: String });
const data = ref(null), error = ref(""), drawer = ref(null);
async function load() {
	data.value = null; error.value = "";
	try { data.value = await call("an_truck_portal.api.records.get_vehicle_form", { vehicle_master: props.name }); }
	catch (e) { error.value = e.message; }
}
onMounted(load);
watch(() => props.name, load);
</script>
<template>
	<div class="page">
		<p v-if="error" class="empty error" role="alert">{{ __(error) }}</p>
		<div v-else-if="!data" class="empty">{{ __("Loading…") }}</div>
		<template v-else>
			<div class="page-head"><div><p class="eyebrow">{{ __("Vehicle Master") }}</p><h1><bdi>{{ data.vin }}</bdi></h1></div><div class="page-actions"><button v-if="data.can_edit" class="button" @click="drawer.open(name, true)">{{ __("Edit Vehicle") }}</button><a class="button secondary" :href="data.desk_url">{{ __("Open in Desk") }}</a></div></div>
			<TemplateSpecifications :template="data.specifications?.template" />
			<section v-for="section in data.sections" :key="section.label" class="panel form-section"><h2>{{ section.label }}</h2><div class="form-grid"><template v-for="field in section.fields" :key="field.fieldname"><div v-if="field.value !== null && field.value !== ''" class="form-field"><small>{{ field.label }}</small><b><a v-if="['Attach', 'Attach Image'].includes(field.fieldtype)" :href="field.value" target="_blank" rel="noopener">{{ __("View current attachment") }}</a><span v-else>{{ field.fieldtype === 'Select' ? __(field.value) : field.value }}</span></b></div></template></div></section>
		</template>
		<VehicleDrawer ref="drawer" @saved="load" />
	</div>
</template>
