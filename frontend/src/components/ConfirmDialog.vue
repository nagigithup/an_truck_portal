<script setup>
import { ref, nextTick } from "vue";
import AppButton from "./AppButton.vue";
import { __ } from "../i18n";
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
		aria-labelledby="discard-title"
		@cancel.prevent="finish(false)"
	>
		<h2 id="discard-title">{{ __("Unsaved changes") }}</h2>
		<p>{{ __("Discard your unsaved changes?") }}</p>
		<div class="form-actions">
			<AppButton variant="secondary" autofocus @click="finish(false)">{{
				__("Keep editing")
			}}</AppButton
			><AppButton @click="finish(true)">{{ __("Discard") }}</AppButton>
		</div>
	</dialog>
</template>
