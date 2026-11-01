<script setup>
import { ref, watch } from "vue";
import { call, __ } from "../api";
const props = defineProps({ template: String });
const data = ref(null), error = ref("");
let generation = 0;
watch(() => props.template, async (template) => {
	const request = ++generation;
	data.value = null; error.value = "";
	if (!template) return;
	try {
		const result = await call("an_truck.an_truck.doctype.vehicle_master.vehicle_master.get_template_specifications", { template_name: template });
		if (request === generation) data.value = result;
	} catch (e) { if (request === generation) error.value = e.message; }
}, { immediate: true });
</script>
<template>
	<details v-if="template" class="vehicle-form-section">
		<summary>{{ __("Linked Technical Specifications") }} · {{ template }}</summary>
		<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
		<p v-else-if="!data">{{ __("Loading…") }}</p>
		<section v-for="section in data?.sections || []" :key="section.label"><h4>{{ section.label }}</h4><dl><template v-for="field in section.fields" :key="field.fieldname"><dt>{{ field.label }}</dt><dd v-if="Array.isArray(field.value)"><div v-for="(row, i) in field.value" :key="i">{{ row.specification_name }}: {{ row.value }} {{ row.uom }}</div></dd><dd v-else-if="field.fieldtype === 'Attach'"><a :href="field.value" target="_blank" rel="noopener">{{ __("View current attachment") }}</a></dd><dd v-else>{{ field.value }}</dd></template></dl></section>
	</details>
</template>
