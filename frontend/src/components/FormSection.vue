<script setup>
import { useId } from "vue";
defineProps({ title: String });
const titleId = useId();
</script>
<template>
	<section class="form-section" :aria-labelledby="titleId">
		<h2 :id="titleId">{{ title }}</h2>
		<div class="form-grid"><slot /></div>
	</section>
</template>
