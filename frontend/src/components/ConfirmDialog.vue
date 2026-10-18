<script setup>
import { ref, nextTick } from "vue";
import AppButton from "./AppButton.vue";
import { __ } from "../i18n";
defineProps({
	title: { default: "Unsaved changes" },
	message: { default: "Discard your unsaved changes?" },
	cancelLabel: { default: "Keep editing" },
	confirmLabel: { default: "Discard" },
});
const dialog = ref(null);
let resolve, previousFocus;
async function ask() {
	previousFocus = document.activeElement;
	await nextTick();
	dialog.value.showModal();
	return new Promise((done) => {
		resolve = done;
	});
}
function finish(value) {
	dialog.value.close();
	resolve?.(value);
	previousFocus?.focus();
}
defineExpose({ ask });
</script>
<template>
	<dialog
		ref="dialog"
		class="confirm-dialog"
		aria-labelledby="confirm-title"
		@cancel.prevent="finish(false)"
	>
		<h2 id="confirm-title">{{ __(title) }}</h2>
		<p>{{ __(message) }}</p>
		<div class="form-actions">
			<AppButton variant="secondary" autofocus @click="finish(false)">{{
				__(cancelLabel)
			}}</AppButton
			><AppButton @click="finish(true)">{{ __(confirmLabel) }}</AppButton>
		</div>
	</dialog>
</template>
