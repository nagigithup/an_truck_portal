<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { call, __ } from "../api";

const props = defineProps({ name: String });
const state = ref("loading");
const error = ref("");
const result = ref(null);
const acknowledgment = computed(() => result.value?.acknowledgment || {});
const company = computed(() => result.value?.company || {});
const letterHead = computed(() => result.value?.letter_head || {});
const sourceDoctype = computed(() =>
	acknowledgment.value.source_doctype || (acknowledgment.value.sales_invoice ? "Sales Invoice" : "Sales Order"),
);
const sourceName = computed(() =>
	acknowledgment.value.source_name || acknowledgment.value.sales_invoice,
);
const backRoute = computed(() => ({
	name: sourceDoctype.value === "Sales Order" ? "sales-order-detail" : "sales-invoice-detail",
	params: { name: sourceName.value },
}));
const accessoryOptions = [
	["main_key", "Main Key"],
	["spare_key", "Spare Key"],
	["spare_tire", "Spare Tire"],
	["jack", "Jack"],
	["tool_kit", "Tool Kit"],
	["fire_extinguisher", "Fire Extinguisher"],
	["warning_triangle", "Warning Triangle"],
	["other", "Other"],
];

function locale() {
	return globalThis.document?.documentElement?.lang || "ar";
}

function date(value) {
	if (!value) return "—";
	try {
		return new Intl.DateTimeFormat(locale(), { dateStyle: "long" }).format(
			new Date(`${value}T00:00:00`),
		);
	} catch {
		return value;
	}
}

async function load() {
	state.value = "loading";
	error.value = "";
	try {
		result.value = await call(
			"an_truck_portal.api.sales.get_vehicle_delivery_acknowledgment",
			{ delivery_note: props.name },
		);
		state.value = "ready";
	} catch (e) {
		error.value = e?.message || __("Unable to load vehicle delivery details.");
		state.value = "error";
	}
}

function printDocument() {
	globalThis.print();
}

onMounted(() => {
	document.body.classList.add("vehicle-delivery-print-mode");
	load();
});
onBeforeUnmount(() => document.body.classList.remove("vehicle-delivery-print-mode"));
watch(() => props.name, load);
</script>

<template>
	<div class="page vehicle-delivery-print-page">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error" role="alert">{{ error }}</div>
		<template v-else>
			<div class="delivery-print-controls">
				<router-link
					class="button secondary"
					:to="backRoute"
				>
					{{ __(sourceDoctype === "Sales Order" ? "Back to Sales Order" : "Back to Sales Invoice") }}
				</router-link>
				<button type="button" class="button" @click="printDocument">{{ __("Print") }}</button>
			</div>

			<article class="delivery-sheet" :dir="locale() === 'ar' ? 'rtl' : 'ltr'">
				<header class="delivery-letter-head">
					<div v-if="letterHead.source === 'HTML' && letterHead.content" v-html="letterHead.content"></div>
					<img
						v-else-if="letterHead.image"
						:src="letterHead.image"
						:alt="company.company_name || company.name"
						:style="{
							width: letterHead.image_width ? `${letterHead.image_width}px` : undefined,
							height: letterHead.image_height ? `${letterHead.image_height}px` : undefined,
						}"
					/>
					<div v-else class="company-fallback">
						<img v-if="company.company_logo" :src="company.company_logo" :alt="company.company_name || company.name" />
						<div><h2>{{ company.company_name || company.name }}</h2><p v-if="company.tax_id">{{ __("Tax ID") }}: {{ company.tax_id }}</p></div>
					</div>
				</header>

				<div class="delivery-title">
					<div><p>{{ __("Vehicle Delivery Acknowledgment") }}</p><h1>{{ __("Vehicle Delivery Note") }}</h1></div>
					<div class="delivery-number"><span>{{ __("Delivery Note") }}</span><bdi>{{ result.delivery_note }}</bdi></div>
				</div>

				<section class="delivery-summary">
					<div><span>{{ __("Customer Name") }}</span><strong>{{ acknowledgment.customer_name }}</strong></div>
					<div><span>{{ __(sourceDoctype) }}</span><strong><bdi>{{ sourceName }}</bdi></strong></div>
					<div><span>{{ __("Delivery Date") }}</span><strong>{{ date(acknowledgment.delivery_date) }}</strong></div>
				</section>

				<section class="delivery-block">
					<h2>{{ __("Vehicle Information") }}</h2>
					<div class="delivery-data-grid">
						<div><span>{{ __("Vehicle Type") }}</span><strong>{{ acknowledgment.vehicle_type || "—" }}</strong></div>
						<div><span>{{ __("Model") }}</span><strong>{{ acknowledgment.model || "—" }}</strong></div>
						<div><span>{{ __("VIN / Chassis Number") }}</span><strong><bdi>{{ acknowledgment.chassis_number || acknowledgment.vin }}</bdi></strong></div>
						<div><span>{{ __("Plate Number") }}</span><strong>{{ acknowledgment.plate_number || "—" }}</strong></div>
						<div class="full"><span>{{ __("Vehicle Description") }}</span><strong>{{ acknowledgment.vehicle_description || "—" }}</strong></div>
					</div>
				</section>

				<section class="delivery-block">
					<h2>{{ __("Vehicle Inspection and Receipt Acknowledgment") }}</h2>
					<p class="acknowledgment-text">{{ __("I acknowledge that I have inspected and received the vehicle described above in its current condition, together with the accessories marked below.") }}</p>
				</section>

				<section class="delivery-block">
					<h2>{{ __("Delivered Accessories") }}</h2>
					<div class="print-accessories">
						<div v-for="([fieldname, label]) in accessoryOptions" :key="fieldname">
							<span class="print-check">{{ acknowledgment.accessories?.[fieldname] ? "☑" : "☐" }}</span>
							<span>{{ __(label) }}</span>
							<small v-if="fieldname === 'other' && acknowledgment.other_description">{{ acknowledgment.other_description }}</small>
						</div>
					</div>
				</section>

				<section class="delivery-block delivery-notes">
					<h2>{{ __("Notes") }}</h2>
					<p>{{ acknowledgment.notes || "—" }}</p>
				</section>

				<section class="delivery-parties">
					<div><span>{{ __("Customer Representative Name") }}</span><strong>{{ acknowledgment.customer_representative_name || "—" }}</strong></div>
					<div><span>{{ __("Representative ID / Iqama Number") }}</span><strong>{{ acknowledgment.representative_id || "—" }}</strong></div>
					<div><span>{{ __("Delivery Employee Name") }}</span><strong>{{ acknowledgment.delivery_employee_name || "—" }}</strong></div>
				</section>

				<section class="delivery-signatures">
					<div><span>{{ __("Customer Signature") }}</span><i></i><small>{{ __("Name and Signature") }}</small></div>
					<div><span>{{ __("Representative Signature") }}</span><i></i><small>{{ __("Name and Signature") }}</small></div>
					<div><span>{{ __("Company Representative Signature") }}</span><i></i><small>{{ __("Name and Signature") }}</small></div>
				</section>

				<footer v-if="letterHead.footer || letterHead.footer_image" class="delivery-letter-footer">
					<div v-if="letterHead.footer_source === 'HTML' && letterHead.footer" v-html="letterHead.footer"></div>
					<img v-else-if="letterHead.footer_image" :src="letterHead.footer_image" alt="" />
				</footer>
			</article>
		</template>
	</div>
</template>

<style>
.vehicle-delivery-print-page {
	max-width: 1040px;
}
.delivery-print-controls {
	display: flex;
	justify-content: flex-end;
	gap: 10px;
	margin-bottom: 16px;
}
.delivery-sheet {
	min-height: 297mm;
	padding: 17mm 16mm;
	background: white;
	color: #171717;
	box-shadow: 0 2px 18px #14213d18;
	font-family: "Noto Sans Arabic", Tahoma, Arial, sans-serif;
}
.delivery-letter-head {
	min-height: 85px;
	border-bottom: 3px solid #262626;
	padding-bottom: 14px;
}
.delivery-letter-head > img {
	display: block;
	max-width: 100%;
	max-height: 100px;
	object-fit: contain;
}
.company-fallback {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 20px;
}
.company-fallback img {
	max-width: 145px;
	max-height: 76px;
}
.company-fallback h2,
.company-fallback p {
	margin: 0;
}
.delivery-title {
	display: flex;
	justify-content: space-between;
	align-items: flex-end;
	gap: 20px;
	padding: 20px 0 15px;
}
.delivery-title p,
.delivery-title h1 {
	margin: 0;
}
.delivery-title p {
	font-size: 12px;
	color: #666;
}
.delivery-title h1 {
	font-size: 25px;
}
.delivery-number {
	display: grid;
	text-align: end;
}
.delivery-number span,
.delivery-summary span,
.delivery-data-grid span,
.delivery-parties span {
	font-size: 10px;
	color: #666;
}
.delivery-summary,
.delivery-parties {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	border: 1px solid #d8d8d8;
}
.delivery-summary > div,
.delivery-parties > div {
	display: grid;
	gap: 5px;
	padding: 11px 13px;
	border-inline-end: 1px solid #d8d8d8;
}
.delivery-summary > div:last-child,
.delivery-parties > div:last-child {
	border-inline-end: 0;
}
.delivery-block {
	margin-top: 16px;
	border: 1px solid #d8d8d8;
}
.delivery-block h2 {
	margin: 0;
	padding: 8px 12px;
	background: #f3f3f3;
	font-size: 13px;
	border-bottom: 1px solid #d8d8d8;
}
.delivery-data-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
}
.delivery-data-grid > div {
	display: grid;
	gap: 3px;
	padding: 9px 12px;
	border-bottom: 1px solid #e6e6e6;
	border-inline-end: 1px solid #e6e6e6;
}
.delivery-data-grid .full {
	grid-column: 1 / -1;
	border-bottom: 0;
}
.acknowledgment-text,
.delivery-notes p {
	margin: 0;
	padding: 12px;
	line-height: 1.8;
}
.print-accessories {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	padding: 5px;
}
.print-accessories > div {
	display: flex;
	align-items: center;
	gap: 7px;
	padding: 8px;
}
.print-accessories small {
	color: #555;
}
.print-check {
	font-size: 18px;
	line-height: 1;
}
.delivery-parties {
	margin-top: 16px;
}
.delivery-signatures {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 18px;
	margin-top: 26px;
}
.delivery-signatures > div {
	display: grid;
	gap: 7px;
	text-align: center;
}
.delivery-signatures i {
	display: block;
	height: 50px;
	border-bottom: 1px solid #555;
}
.delivery-signatures small {
	color: #777;
}
.delivery-letter-footer {
	margin-top: 24px;
	padding-top: 10px;
	border-top: 1px solid #d8d8d8;
}
.delivery-letter-footer img {
	max-width: 100%;
}
@media print {
	@page {
		size: A4;
		margin: 0;
	}
	body.vehicle-delivery-print-mode {
		background: white;
	}
	body.vehicle-delivery-print-mode .sidebar,
	body.vehicle-delivery-print-mode .top-header,
	body.vehicle-delivery-print-mode .notice,
	body.vehicle-delivery-print-mode .delivery-print-controls {
		display: none !important;
	}
	body.vehicle-delivery-print-mode .main {
		margin: 0;
	}
	body.vehicle-delivery-print-mode .vehicle-delivery-print-page {
		max-width: none;
		padding: 0;
	}
	.delivery-sheet {
		min-height: 297mm;
		box-shadow: none;
		break-after: page;
	}
}
</style>
