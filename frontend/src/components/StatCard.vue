<script setup>
defineProps({ label: String, value: [String, Number], caption: String });
</script>
<template>
	<article class="metric">
		<small>{{ label }}</small
		><strong class="ltr-value">{{ value }}</strong
		><span v-if="caption">{{ caption }}</span>
	</article>
</template>
