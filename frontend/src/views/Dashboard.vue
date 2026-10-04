<script setup>
import { inject, onMounted, ref } from "vue";
import { call, __ } from "../api";
import PageHeader from "../components/PageHeader.vue";
import AppCard from "../components/AppCard.vue";
import StatCard from "../components/StatCard.vue";
import LoadingState from "../components/LoadingState.vue";
import EmptyState from "../components/EmptyState.vue";
import AppButton from "../components/AppButton.vue";
const { ctx } = inject("portal"),
	state = ref("loading"),
	data = ref({}),
	error = ref("");
async function load() {
	state.value = "loading";
	try {
		data.value = await call("an_truck_portal.api.dashboard.get_dashboard", {
			company: ctx.company,
		});
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}
onMounted(load);
</script>
<template>
	<div class="page">
		<PageHeader
			:eyebrow="__('Operations')"
			:title="__('Home')"
			:subtitle="__('Truck import, purchasing, vehicles and sales at a glance.')"
		/>
		<LoadingState v-if="state === 'loading'" />
		<EmptyState v-else-if="state === 'error'" :message="__(error)" error
			><AppButton @click="load">{{ __("Retry") }}</AppButton></EmptyState
		>
		<template v-else
			><div class="cards">
				<StatCard
					v-for="card in data.cards"
					:key="card.label"
					:label="__(card.label)"
					:value="
						card.state === 'ready'
							? String(card.value) + (card.capped ? '+' : '')
							: __('Not available')
					"
				/>
			</div>
			<div class="columns">
				<AppCard :title="__('Recently updated import files')"
					><div v-if="data.recent_imports?.length" class="rows">
						<router-link
							v-for="record in data.recent_imports"
							:key="record.name"
							:to="'/import-files/' + encodeURIComponent(record.name)"
							><b>{{ record.import_title || record.name }}</b
							><small
								>{{ record.supplier }} · {{ __(record.status) }}</small
							></router-link
						>
					</div>
					<EmptyState
						v-else
						:message="
							__(data.recent_imports === null ? 'Not available' : 'No records')
						"
				/></AppCard>
				<AppCard :title="__('Vehicles requiring attention')"
					><div v-if="data.vehicles?.length" class="rows">
						<router-link
							v-for="record in data.vehicles"
							:key="record.name"
							:to="'/vehicles/' + encodeURIComponent(record.name)"
							><b class="ltr-value">{{ record.vin }}</b
							><small
								>{{ record.brand }} {{ record.model }} ·
								{{ __(record.vehicle_status) }}</small
							></router-link
						>
					</div>
					<EmptyState
						v-else
						:message="__(data.vehicles === null ? 'Not available' : 'No records')"
				/></AppCard></div
		></template>
	</div>
</template>
