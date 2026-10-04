<script setup>
defineProps({ title: String, subtitle: String, eyebrow: String });
</script>
<template>
	<div class="page-head">
		<div>
			<p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
			<h1>{{ title }}</h1>
			<p v-if="subtitle">{{ subtitle }}</p>
		</div>
		<div class="page-actions"><slot /></div>
	</div>
</template>
