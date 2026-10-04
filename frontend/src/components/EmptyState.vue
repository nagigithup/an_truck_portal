<script setup>
defineProps({ message: String, error: Boolean });
</script>
<template>
	<div :class="['empty', { error }]" :role="error ? 'alert' : 'status'">
		<p>{{ message }}</p>
		<slot />
	</div>
</template>
