<script setup>
defineProps({ title: String });
</script>
<template>
	<section class="panel">
		<h2 v-if="title">{{ title }}</h2>
		<slot />
	</section>
</template>
