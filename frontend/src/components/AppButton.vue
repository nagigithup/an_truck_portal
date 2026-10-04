<script setup>
defineProps({ variant: { default: "primary" }, busy: Boolean, type: { default: "button" } });
</script>
<template>
	<button :type="type" :class="['button', variant]" :disabled="busy" :aria-busy="busy">
		<slot />
	</button>
</template>
