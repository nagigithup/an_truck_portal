<script setup>
import { computed, ref, useId, watch, onBeforeUnmount } from "vue";
import { __ } from "../i18n";
import { call } from "../api";
const props = defineProps({
	modelValue: [String, Number, Boolean],
	label: String,
	type: { default: "text" },
	required: Boolean,
	disabled: Boolean,
	loading: Boolean,
	options: Array,
	link: Object,
	ltr: Boolean,
	rows: { type: Number, default: 3 },
});
const emit = defineEmits(["update:modelValue"]);
const id = useId(),
	suggestions = ref([]),
	error = ref("");
const selectOptions = computed(() => {
	const options = props.options || [];
	const current = props.modelValue;
	// Preserve the saved value while options arrive, including inactive or
	// restricted historical values. Do not offer these as new selections.
	if (
		current !== undefined &&
		current !== null &&
		current !== "" &&
		!options.some((option) => String(option.value ?? option) === String(current))
	) {
		return [{ value: current, label: current, disabled: true }, ...options];
	}
	return options;
});
let timer,
	generation = 0;
async function search(value = "") {
	if (!props.link || props.disabled) return;
	const request = ++generation;
	try {
		const rows = await call("an_truck.portal_parties.link_options", {
			...props.link,
			search: value,
		});
		if (request === generation) {
			suggestions.value = rows;
			error.value = "";
		}
	} catch (e) {
		if (request === generation) error.value = e.message;
	}
}
watch(
	() => props.modelValue,
	(value) => {
		clearTimeout(timer);
		timer = setTimeout(() => search(value || ""), 250);
	},
);
onBeforeUnmount(() => {
	clearTimeout(timer);
	generation++;
});
</script>
<template>
	<div class="form-field">
		<label :for="id"
			>{{ label }}
			<span v-if="required" class="required" aria-hidden="true" :title="__('Required')"
				>*</span
			></label
		>
		<textarea
			v-if="type === 'textarea'"
			:id="id"
			:value="modelValue"
			:required="required"
			:disabled="disabled"
			:rows="rows"
			@input="emit('update:modelValue', $event.target.value)"
		/>
		<select
			v-else-if="type === 'select'"
			:id="id"
			:value="modelValue"
			:required="required"
			:disabled="disabled || loading"
			:aria-busy="loading"
			@change="emit('update:modelValue', $event.target.value)"
		>
			<option value="">{{ __(loading ? "Loading..." : "Select") }}</option>
			<option
				v-for="option in selectOptions"
				:key="option.value ?? option"
				:value="option.value ?? option"
				:disabled="option.disabled || false"
			>
				{{ __(option.label ?? option) }}
			</option>
		</select>
		<input
			v-else
			:id="id"
			:type="type"
			:class="{ 'ltr-value': ltr }"
			:value="modelValue"
			:required="required"
			:disabled="disabled"
			:list="link ? `${id}-options` : undefined"
			:aria-describedby="error ? `${id}-error` : undefined"
			@focus="search(modelValue || '')"
			@input="emit('update:modelValue', $event.target.value)"
		/>
		<datalist v-if="link" :id="`${id}-options`">
			<option v-for="value in suggestions" :key="value" :value="value" />
		</datalist>
		<small v-if="error" :id="`${id}-error`" class="error">{{ __(error) }}</small>
	</div>
</template>
