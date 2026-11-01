<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { call, uploadFile, __ } from "../api";
import FormField from "../components/FormField.vue";
import LinkedVehiclesDialog from "../components/LinkedVehiclesDialog.vue";
const rows = ref([]), hasMore = ref(false), page = ref(1), search = ref(""), error = ref(""), loading = ref(false), canCreate = ref(false);
const dialog = ref(null), current = ref(null), values = ref({}), busy = ref(false), linked = ref(null), attachments = ref({});
const base = "an_truck_portal.api.specifications.";
const { ctx } = inject("portal");
const visibleSections = computed(() => (current.value?.sections || [])
	.map(section => ({ ...section, fields: section.fields.filter(field => !["technical_specifications", "specifications"].includes(field.fieldname)) }))
	.filter(section => section.fields.length));
async function load() {
	loading.value = true; error.value = "";
	try { const data = await call(base + "list_templates", { search: search.value, page: page.value }); rows.value = data.rows; hasMore.value = data.has_more; canCreate.value = data.can_create; }
	catch (e) { error.value = e.message; } finally { loading.value = false; }
}
async function open(name = null) {
	error.value = ""; attachments.value = {};
	try { current.value = await call(base + "get_template", { name, company: ctx.company }); values.value = Object.fromEntries(current.value.sections.flatMap(s => s.fields.map(f => [f.fieldname, f.value ?? ""]))); dialog.value.showModal(); }
	catch (e) { error.value = e.message; }
}
function type(field) {
	if (["Float", "Int"].includes(field.fieldtype)) return "number";
	if (field.fieldtype === "Select") return "select";
	if (["Small Text", "Long Text"].includes(field.fieldtype)) return "textarea";
	return "text";
}
async function save() {
	busy.value = true; error.value = "";
	try {
		const writable = visibleSections.value.flatMap(s => s.fields).filter(f => !f.read_only && (current.value.status === 'Draft' || f.fieldname === 'active'));
		const data = Object.fromEntries(writable.map(f => [f.fieldname, values.value[f.fieldname]]));
		const result = await call(base + "save_template", { name: current.value.name, modified: current.value.modified, values: data }, true);
		for (const [fieldname, file] of Object.entries(attachments.value)) {
			if (!file) continue;
			const uploaded = await uploadFile(file, "Vehicle Specification Template", result.name);
			const fresh = await call(base + "get_template", { name: result.name });
			await call(base + "save_template", { name: result.name, modified: fresh.modified, values: { [fieldname]: uploaded.file_url } }, true);
		}
		dialog.value.close(); await load(); await open(result.name);
		return result.name;
	} catch (e) { error.value = e.message; } finally { busy.value = false; }
}
async function action(method) {
	if (method === "publish_template" && !(await save())) return;
	busy.value = true; error.value = "";
	try { const result = await call(base + method, { name: current.value.name }, true); dialog.value.close(); await load(); await open(result.name); }
	catch (e) { error.value = e.message; } finally { busy.value = false; }
}
onMounted(load);
</script>
<template>
	<div class="page">
		<div class="page-head"><h1>{{ __("Vehicle Specification Templates") }}</h1><div class="page-actions"><input v-model="search" :placeholder="__('Search…')" @keyup.enter="page = 1; load()" /><button class="button secondary" @click="page = 1; load()">{{ __("Search") }}</button><button v-if="canCreate" class="button" @click="open()">{{ __("New Specification Template") }}</button></div></div>
		<p v-if="error" class="notice error-notice" role="alert">{{ __(error) }}</p>
		<div v-if="loading" class="empty">{{ __("Loading…") }}</div>
		<div v-else class="panel table-wrap"><table><thead><tr><th>{{ __("Template Name") }}</th><th>{{ __("Revision") }}</th><th>{{ __("Item Code") }}</th><th>{{ __("Status") }}</th><th>{{ __("Actions") }}</th></tr></thead><tbody><tr v-if="!rows.length"><td colspan="5" class="empty">{{ __("No records found") }}</td></tr><tr v-for="row in rows" :key="row.name"><td>{{ row.template_name }}</td><td>{{ row.revision }}</td><td>{{ row.item_code || '—' }}</td><td>{{ __(row.status) }}</td><td><button class="text-button" @click="open(row.name)">{{ __("View") }}</button></td></tr></tbody></table></div>
		<div class="pagination"><button class="button secondary" :disabled="page <= 1 || loading" @click="page--; load()">{{ __("Previous") }}</button><span>{{ __("Page") }} {{ page }}</span><button class="button secondary" :disabled="!hasMore || loading" @click="page++; load()">{{ __("Next") }}</button></div>
		<dialog ref="dialog" class="operation-dialog wide-dialog" :aria-label="__('Specification Template')" @cancel.prevent="!busy && dialog.close()">
			<form v-if="current" @submit.prevent="save">
				<div class="dialog-head"><h2>{{ current.name || __("New Specification Template") }}</h2><button type="button" class="icon" :disabled="busy" :aria-label="__('Close')" @click="dialog.close()">×</button></div>
				<div class="dialog-body">
					<button v-if="current.name && current.linked_count !== null" type="button" class="button secondary" @click="linked.open()">{{ __("View Linked Vehicles") }} ({{ current.linked_count }})</button>
					<section v-for="section in visibleSections" :key="section.label" class="form-section"><h3>{{ section.label }}</h3><div class="form-grid">
						<template v-for="field in section.fields" :key="field.fieldname">
							<div v-if="field.fieldtype === 'Table'" class="field-span-full"><h4>{{ field.label }}</h4><div v-for="(row, index) in values[field.fieldname]" :key="index" class="form-grid"><FormField v-for="key in ['specification_category', 'specification_name', 'value', 'uom', 'notes']" :key="key" v-model="row[key]" :label="__({ specification_category: 'Specification Category', specification_name: 'Specification Name', value: 'Value', uom: 'UOM', notes: 'Notes' }[key])" :disabled="current.status !== 'Draft' || !current.can_write" /><button v-if="current.status === 'Draft' && current.can_write" type="button" class="text-button" @click="values[field.fieldname].splice(index, 1)">{{ __("Delete") }}</button></div><button v-if="current.status === 'Draft' && current.can_write" type="button" class="button secondary" @click="values[field.fieldname].push({ specification_category: '', specification_name: '', value: '', uom: '', notes: '' })">{{ __("Add Specification") }}</button></div>
							<label v-else-if="field.fieldtype === 'Check'"><input v-model="values[field.fieldname]" type="checkbox" :true-value="1" :false-value="0" :disabled="!current.can_write || (current.status !== 'Draft' && field.fieldname !== 'active')" />{{ field.label }}</label>
							<div v-else-if="field.fieldtype === 'Attach'" class="form-field"><label>{{ field.label }}</label><input type="file" :disabled="busy || current.status !== 'Draft' || !current.can_write" @change="attachments[field.fieldname] = $event.target.files?.[0]" /><a v-if="values[field.fieldname]" :href="values[field.fieldname]" target="_blank" rel="noopener">{{ __("View current attachment") }}</a></div>
							<FormField v-else v-model="values[field.fieldname]" :label="field.label" :type="type(field)" :step="field.fieldtype === 'Float' ? 'any' : undefined" :options="(field.options || '').split('\n').filter(Boolean)" :link="field.fieldtype === 'Link' ? { doctype: field.options } : undefined" :required="field.required" :disabled="busy || field.read_only || !current.can_write || current.status !== 'Draft'" />
						</template>
					</div></section>
					<p v-if="error" class="form-error" role="alert">{{ __(error) }}</p>
				</div>
				<div class="dialog-actions"><button type="button" class="button secondary" :disabled="busy" @click="dialog.close()">{{ __("Close") }}</button><button v-if="current.can_write" class="button" :disabled="busy">{{ __("Save") }}</button><button v-if="current.name && current.status === 'Draft' && current.can_write" type="button" class="button" :disabled="busy" @click="action('publish_template')">{{ __("Publish Template") }}</button><button v-if="current.status === 'Published' && current.can_create" type="button" class="button" :disabled="busy" @click="action('create_revision')">{{ __("Create New Revision") }}</button></div>
			</form>
		</dialog>
		<LinkedVehiclesDialog v-if="current?.name" ref="linked" :template="current.name" />
	</div>
</template>
