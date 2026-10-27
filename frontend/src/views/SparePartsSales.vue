<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { call, __ } from "../api";
import AppButton from "../components/AppButton.vue";
import AppCard from "../components/AppCard.vue";
import DataTable from "../components/DataTable.vue";
import EmptyState from "../components/EmptyState.vue";
import FilterBar from "../components/FilterBar.vue";
import LoadingState from "../components/LoadingState.vue";
import PageHeader from "../components/PageHeader.vue";
import SearchInput from "../components/SearchInput.vue";
import SparePartsSalesDialog from "../components/SparePartsSalesDialog.vue";

const { ctx } = inject("portal");
const router = useRouter();
const rows = ref([]), search = ref(""), page = ref(1), more = ref(false), state = ref("loading"), error = ref(""), dialog = ref(null);
const columns = computed(() => ["Sales Invoice", "Customer", "Posting Date", "Company", "Price List", "Grand Total", "Outstanding Amount", "Status", "Actions"].map((label) => ({ key: label.toLowerCase().replaceAll(" ", "_"), label: __(label) })));
let timer;
async function load() {
	state.value = "loading";
	try { const result = await call("an_truck_portal.api.spare_parts_sales.list_invoices", { search: search.value, company: ctx.company, page: page.value }); rows.value = result.rows; more.value = result.has_more; state.value = "ready"; }
	catch (e) { error.value = e.message; state.value = "error"; }
}
watch(search, () => { page.value = 1; clearTimeout(timer); timer = setTimeout(load, 250); });
onMounted(load);
function created(result) { load(); router.push({ name: "spare-parts-sale-detail", params: { name: result.name } }); }
</script>
<template><div class="page"><PageHeader :title="__('Spare Parts Sales')" :subtitle="__('Stock-updating spare-parts Sales Invoices using standard price lists.')"><button v-if="ctx.permissions['Sales Invoice']?.create" class="button" @click="dialog.open()">+ {{ __("New Spare Parts Sale") }}</button></PageHeader><AppCard><FilterBar><SearchInput v-model="search" :placeholder="__('Search invoices or customers…')" /></FilterBar><LoadingState v-if="state === 'loading'" /><EmptyState v-else-if="state === 'error'" :message="__(error)" error><AppButton @click="load">{{ __("Retry") }}</AppButton></EmptyState><EmptyState v-else-if="!rows.length" :message="__('No spare-parts sales invoices found.')" /><DataTable v-else :columns="columns" :rows="rows" :caption="__('Spare Parts Sales')"><template #sales_invoice="{ row }"><bdi>{{ row.name }}</bdi></template><template #customer="{ row }">{{ row.customer_name || row.customer }}</template><template #price_list="{ row }">{{ row.selling_price_list }}</template><template #grand_total="{ row }">{{ row.grand_total }} {{ row.currency }}</template><template #outstanding_amount="{ row }">{{ row.outstanding_amount }} {{ row.currency }}</template><template #status="{ row }">{{ __(row.docstatus === 0 ? 'Draft' : row.status) }}</template><template #actions="{ row }"><router-link class="text-button" :to="{ name: 'spare-parts-sale-detail', params: { name: row.name } }">{{ __("View") }}</router-link></template></DataTable><div class="pagination"><span>{{ __("Page") }} <bdi>{{ page }}</bdi></span><div class="row-actions"><AppButton variant="secondary" :disabled="page === 1" @click="page--; load()">{{ __("Previous") }}</AppButton><AppButton variant="secondary" :disabled="!more" @click="page++; load()">{{ __("Next") }}</AppButton></div></div></AppCard><SparePartsSalesDialog ref="dialog" @created="created" /></div></template>
