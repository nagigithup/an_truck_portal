<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({
	doctype: { type: String, required: true },
	documentName: { type: String, required: true },
});

const dialog = ref(null);
const previewFrame = ref(null);
const loading = ref(false);
const previewLoading = ref(false);
const error = ref("");
const formats = ref([]);
const selectedFormat = ref("");
const previewUrl = ref("");
const renderedUrl = ref("");
const printAfterLoad = ref(false);

const canRender = computed(
	() => !loading.value && !!selectedFormat.value && !!props.documentName,
);

function printViewUrl() {
	const params = new URLSearchParams({
		doctype: props.doctype,
		name: props.documentName,
		format: selectedFormat.value || "Standard",
		no_letterhead: "0",
		_lang: globalThis.document?.documentElement?.lang || "en",
	});
	return `/printview?${params.toString()}`;
}

async function open() {
	error.value = "";
	formats.value = [];
	selectedFormat.value = "";
	previewUrl.value = "";
	renderedUrl.value = "";
	printAfterLoad.value = false;
	loading.value = true;
	dialog.value?.showModal();
	try {
		const result = await call("an_truck_portal.api.sales.get_sales_print_options", {
			doctype: props.doctype,
			document: props.documentName,
		});
		formats.value = Array.isArray(result?.formats) ? result.formats : [];
		selectedFormat.value = result?.default_format || formats.value[0] || "";
	} catch (e) {
		error.value = e?.message || __("Unable to load print options.");
	} finally {
		loading.value = false;
	}
}

function close() {
	if (!loading.value && !previewLoading.value) dialog.value?.close();
}

function showPreview() {
	if (!canRender.value) return;
	error.value = "";
	printAfterLoad.value = false;
	previewLoading.value = true;
	previewUrl.value = printViewUrl();
}

async function printDocument() {
	if (!canRender.value) return;
	error.value = "";
	const url = printViewUrl();
	if (renderedUrl.value === url && previewFrame.value?.contentWindow) {
		try {
			previewFrame.value.contentWindow.print();
		} catch {
			error.value = __("Unable to open print preview.");
		}
		return;
	}
	printAfterLoad.value = true;
	previewLoading.value = true;
	previewUrl.value = url;
	await nextTick();
}

function previewLoaded() {
	renderedUrl.value = previewUrl.value;
	previewLoading.value = false;
	if (!printAfterLoad.value) return;
	printAfterLoad.value = false;
	try {
		previewFrame.value?.contentWindow?.print();
	} catch {
		error.value = __("Unable to open print preview.");
	}
}

watch(selectedFormat, () => {
	if (previewUrl.value && renderedUrl.value !== printViewUrl()) {
		previewUrl.value = "";
		renderedUrl.value = "";
	}
});

defineExpose({ open });
</script>

<template>
	<dialog
		ref="dialog"
		class="operation-dialog print-dialog"
		:class="{ 'wide-dialog': previewUrl }"
		:aria-label="__('Print')"
		@cancel.prevent="close"
	>
		<form @submit.prevent="printDocument">
			<div class="dialog-head">
				<div><p class="eyebrow">{{ __(doctype) }}</p><h2>{{ __("Print") }}</h2></div>
				<button type="button" class="icon" :aria-label="__('Close')" @click="close">×</button>
			</div>
			<div class="dialog-body print-dialog-body">
				<label class="print-format-field">
					<span>{{ __("Print Format") }}</span>
					<select v-model="selectedFormat" :disabled="loading" required>
						<option value="">{{ loading ? __("Loading print formats…") : __("Select") }}</option>
						<option v-for="format in formats" :key="format" :value="format">
							{{ format === "Standard" ? __("Standard") : format }}
						</option>
					</select>
				</label>
				<p v-if="error" class="form-error" role="alert">{{ error }}</p>
				<div v-if="previewUrl" class="print-preview-shell">
					<p v-if="previewLoading" class="empty compact">{{ __("Loading…") }}</p>
					<iframe
						ref="previewFrame"
						class="print-preview-frame"
						:class="{ loading: previewLoading }"
						:src="previewUrl"
						:title="__('Print Preview')"
						@load="previewLoaded"
					></iframe>
				</div>
			</div>
			<div class="dialog-actions">
				<button type="button" class="button secondary" :disabled="loading || previewLoading" @click="close">{{ __("Cancel") }}</button>
				<button type="button" class="button secondary" :disabled="!canRender || previewLoading" @click="showPreview">{{ __("Print Preview") }}</button>
				<button class="button" :disabled="!canRender || previewLoading">{{ __("Print") }}</button>
			</div>
		</form>
	</dialog>
</template>

<style scoped>
.print-dialog:not(.wide-dialog) {
	width: min(520px, calc(100vw - 32px));
}
.print-dialog-body {
	display: grid;
	gap: 16px;
}
.print-format-field {
	display: flex;
	flex-direction: column;
	gap: 5px;
}
.print-format-field > span {
	font-size: 11px;
	font-weight: 600;
	color: var(--muted);
}
.print-preview-shell {
	position: relative;
	min-height: 62vh;
	border: 1px solid var(--line);
	border-radius: 7px;
	overflow: hidden;
	background: white;
}
.print-preview-shell > .empty {
	position: absolute;
	inset: 0;
	z-index: 1;
	display: grid;
	place-items: center;
	background: white;
}
.print-preview-frame {
	display: block;
	width: 100%;
	height: 62vh;
	border: 0;
	background: white;
}
.print-preview-frame.loading {
	visibility: hidden;
}
</style>
