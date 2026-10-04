<script setup>
import IconSearch from "~icons/lucide/search";
import { __ } from "../i18n";
defineProps({ modelValue: String, placeholder: String });
defineEmits(["update:modelValue"]);
</script>
<template>
	<div class="search">
		<IconSearch aria-hidden="true" /><input
			type="search"
			:value="modelValue"
			:aria-label="placeholder || __('Search')"
			:placeholder="placeholder || __('Search…')"
			@input="$emit('update:modelValue', $event.target.value)"
		/><slot />
	</div>
</template>
