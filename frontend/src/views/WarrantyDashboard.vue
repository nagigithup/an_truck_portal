<script setup>
import { inject, onMounted, ref } from "vue";
import { call, __ } from "../api";

const { ctx } = inject("portal");
const state = ref("loading");
const error = ref("");
const data = ref({ cards: [], recent_warranties: [], recent_claims: [] });

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		data.value = await call("an_truck_portal.api.warranty.get_dashboard", {
			company: ctx.company,
		});
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}
onMounted(load);

function date(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat(document.documentElement.lang || "en", {
		dateStyle: "medium",
	}).format(new Date(`${String(value).slice(0, 10)}T00:00:00`));
}
</script>

<template>
	<div class="page warranty-page">
		<header class="page-head">
			<div><p class="eyebrow">{{ __("Warranty") }}</p><h1>{{ __("Warranty Dashboard") }}</h1><p>{{ __("Warranty coverage and claims at a glance.") }}</p></div>
		</header>
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error">{{ error }}</div>
		<template v-else>
			<section class="cards warranty-cards" :aria-label="__('Warranty summary')">
				<article v-for="card in data.cards" :key="card.label" class="metric"><small>{{ __(card.label) }}</small><strong>{{ card.value }}</strong></article>
			</section>
			<div class="columns">
				<section class="panel"><h2>{{ __("Recent Warranties") }}</h2><div v-if="data.recent_warranties.length" class="rows">
					<router-link v-for="row in data.recent_warranties" :key="row.name" :to="`/warranties/${encodeURIComponent(row.name)}`"><bdi><strong>{{ row.vin }}</strong></bdi><small>{{ row.customer }} · {{ __(row.status) }} · {{ date(row.warranty_expiry_date) }}</small></router-link>
				</div><div v-else class="empty">{{ __("No warranties found.") }}</div></section>
				<section class="panel"><h2>{{ __("Recent Claims") }}</h2><div v-if="data.recent_claims.length" class="rows">
					<router-link v-for="row in data.recent_claims" :key="row.name" :to="`/warranty-claims/${encodeURIComponent(row.name)}`"><bdi><strong>{{ row.name }}</strong></bdi><small>{{ row.vin }} · {{ __(row.status) }} · {{ date(row.claim_date) }}</small></router-link>
				</div><div v-else class="empty">{{ __("No claims found.") }}</div></section>
			</div>
		</template>
	</div>
</template>
