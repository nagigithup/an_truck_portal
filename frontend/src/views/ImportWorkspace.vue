<script setup>
import { computed, inject, nextTick, onMounted, ref } from "vue";
import { call, uploadFile, __ } from "../api";
import ConfirmDialog from "../components/ConfirmDialog.vue";
import PurchaseOrderDialog from "../components/PurchaseOrderDialog.vue";
import VehicleDrawer from "../components/VehicleDrawer.vue";

const props = defineProps({ name: String });
const { notification } = inject("portal");
const state = ref("loading");
const error = ref("");
const workspace = ref(null);
const busy = ref("");
const actionError = ref("");
const vinQuery = ref("");
const vinSearching = ref(false);
const vinResult = ref(undefined);
const highlightedVin = ref("");
const vehicleDrawer = ref(null);
const options = ref(null);
const purchaseDialog = ref(null);
const receivingDialog = ref(null);
const costDialog = ref(null);
const closeFileConfirm = ref(null);
const closeFileError = ref("");

const receiptForm = ref({ purchase_order: "", posting_date: "", items: [], vins: [] });
const costForm = ref({ posting_date: "", allocation_basis: "Qty", receipts: [], rows: [] });
const costCreationResult = ref(null);
const operationKey = ref("");

const data = computed(() => workspace.value || {});
const summary = computed(() => data.value.summary || {});
const permissions = computed(() => data.value.permissions || {});
const canCreatePO = computed(() => data.value.next_actions?.includes("create_purchase_order"));
const canReceive = computed(() => data.value.next_actions?.includes("receive_vehicles"));
const canAddCost = computed(() => data.value.next_actions?.includes("add_import_cost"));
const canCloseFile = computed(() => data.value.next_actions?.includes("close_import_file"));
const isCompleted = computed(() => data.value.import_file?.status === "Completed");
const submittedReceipts = computed(() =>
	(data.value.documents?.purchase_receipts || []).filter((row) => row.docstatus === 1),
);

function key() {
	return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
}
function amount(value, currency = summary.value.currency) {
	if (value == null || value === "") return "—";
	try {
		return new Intl.NumberFormat(document.documentElement.lang, {
			style: "currency",
			currency: currency || "USD",
			maximumFractionDigits: 2,
		}).format(Number(value));
	} catch {
		return `${Number(value).toLocaleString()} ${currency || ""}`;
	}
}
function date(value) {
	if (!value) return "—";
	return new Intl.DateTimeFormat(document.documentElement.lang, { dateStyle: "medium" }).format(
		new Date(String(value).replace(" ", "T")),
	);
}
function docStatus(row) {
	return row?.docstatus === 2
		? __("Cancelled")
		: row?.docstatus === 1
			? __("Submitted")
			: __("Draft");
}
function desk(doctype, name) {
	return `/app/${doctype.toLowerCase().replaceAll(" ", "-")}/${encodeURIComponent(name)}`;
}
function documentDoctype(group) {
	return {
		purchase_orders: "Purchase Order",
		purchase_receipts: "Purchase Receipt",
		purchase_invoices: "Purchase Invoice",
		supplier_payments: "Payment Entry",
		landed_cost_vouchers: "Landed Cost Voucher",
		quotations: "Quotation",
		sales_orders: "Sales Order",
		delivery_notes: "Delivery Note",
		sales_invoices: "Sales Invoice",
		customer_payments: "Payment Entry",
	}[group];
}
function documentRoute(group, name) {
	return {
		purchase_orders: { name: "purchase-order-detail", params: { name } },
		purchase_receipts: { name: "purchase-receipt-detail", params: { name } },
		purchase_invoices: { name: "purchase-invoice-detail", params: { name } },
		supplier_payments: { name: "supplier-payment-detail", params: { name } },
		landed_cost_vouchers: { name: "landed-cost-detail", params: { name } },
	}[group];
}
async function load() {
	state.value = "loading";
	error.value = "";
	try {
		workspace.value = await call("an_truck.transactions.get_import_workspace", {
			vehicle_import_file: props.name,
		});
		state.value = "ready";
	} catch (e) {
		error.value = e.message;
		state.value = "error";
	}
}
async function loadOptions() {
	if (!options.value)
		options.value = await call("an_truck.transactions.get_import_form_options", {
			vehicle_import_file: props.name,
		});
	return options.value;
}
function show(dialog) {
	actionError.value = "";
	operationKey.value = key();
	dialog.value?.showModal();
}
function close(dialog) {
	if (!busy.value) (dialog?.value || dialog)?.close();
}
async function runAction(name, method, args, dialog) {
	if (busy.value) return;
	busy.value = name;
	actionError.value = "";
	try {
		const result = await call(
			method,
			{ vehicle_import_file: props.name, ...args, idempotency_key: operationKey.value },
			true,
		);
		dialog.value?.close();
		notification.value = __("Operation completed successfully: {0}", [result.name || ""]);
		await load();
	} catch (e) {
		actionError.value = e.message || __("Unable to complete the operation");
	} finally {
		busy.value = "";
	}
}

async function completeImportFile() {
	if (busy.value || !(await closeFileConfirm.value?.ask())) return;
	busy.value = "close-file";
	closeFileError.value = "";
	try {
		await call(
			"an_truck_portal.api.import_file.complete_import_file",
			{ vehicle_import_file: props.name },
			true,
		);
		notification.value = __("Vehicle Import File completed successfully.");
		await load();
	} catch (e) {
		closeFileError.value = e.message || __("Unable to complete the operation");
	} finally {
		busy.value = "";
	}
}

function openPurchase() {
	purchaseDialog.value?.open();
}

async function openReceiving() {
	const opts = await loadOptions();
	const po = data.value.receiving?.purchase_orders?.[0]?.name;
	if (!po) return;
	const items = await call("an_truck.transactions.get_purchase_order_items", {
		purchase_order: po,
		vehicle_import_file: props.name,
	});
	receiptForm.value = {
		purchase_order: po,
		posting_date: opts.today,
		items: items.map((row) => ({ ...row, qty: row.remaining_qty })),
		vins: [],
	};
	syncVins();
	show(receivingDialog);
}
async function changeReceiptPO() {
	const items = await call("an_truck.transactions.get_purchase_order_items", {
		purchase_order: receiptForm.value.purchase_order,
		vehicle_import_file: props.name,
	});
	receiptForm.value.items = items.map((row) => ({ ...row, qty: row.remaining_qty }));
	receiptForm.value.vins = [];
	syncVins();
}
function syncVins() {
	const old = receiptForm.value.vins;
	const next = [];
	for (const item of receiptForm.value.items) {
		if (!item.is_vehicle_item) continue;
		const count = Math.max(0, Math.floor(Number(item.qty) || 0));
		const existing = old.filter((row) => row.purchase_order_item === item.purchase_order_item);
		for (let index = 0; index < count; index++)
			next.push(
				existing[index] || {
					purchase_order_item: item.purchase_order_item,
					item_code: item.item_code,
					vin: "",
				},
			);
	}
	receiptForm.value.vins = next;
}
function nextVin(index) {
	document.querySelector(`[data-vin-index="${index + 1}"]`)?.focus();
}
function submitReceipt() {
	const items = receiptForm.value.items
		.filter((row) => Number(row.qty) > 0)
		.map((row) => ({
			purchase_order_item: row.purchase_order_item,
			item_code: row.item_code,
			qty: Number(row.qty),
			warehouse: row.warehouse,
		}));
	const vins = receiptForm.value.vins.map((row) => ({
		item_code: row.item_code,
		vin: row.vin.trim(),
	}));
	const normalized = vins.map((row) => row.vin).filter(Boolean);
	if (!items.length)
		return void (actionError.value = __("Select at least one quantity to receive."));
	if (vins.some((row) => !row.vin))
		return void (actionError.value = __("Enter every VIN before submitting the receipt."));
	if (new Set(normalized).size !== normalized.length)
		return void (actionError.value = __("Duplicate VIN in this receipt."));
	runAction(
		"receipt",
		"an_truck_portal.api.import_file.create_purchase_receipt",
		{
			data: {
				purchase_order: receiptForm.value.purchase_order,
				posting_date: receiptForm.value.posting_date,
				items,
				vins,
			},
			submit_now: 1,
		},
		receivingDialog,
	);
}

async function openCost() {
	const opts = await loadOptions();
	costCreationResult.value = null;
	costForm.value = {
		posting_date: opts.today,
		allocation_basis: "Qty",
		receipts: submittedReceipts.value.map((row) => row.name),
		rows: [
			{
				cost_type: "Customs",
				supplier: "",
				amount: 0,
				expense_account: "",
				reference: "",
				notes: "",
				attachment: null,
				attachment_uploaded: false,
			},
		],
	};
	show(costDialog);
}
function addCostRow() {
	costForm.value.rows.push({
		cost_type: "Other Direct Costs",
		supplier: "",
		amount: 0,
		expense_account: "",
		reference: "",
		notes: "",
		attachment: null,
		attachment_uploaded: false,
	});
}
function selectCostAttachment(row, event) {
	const file = event.target.files?.[0] || null;
	if (
		file &&
		!["application/pdf", "image/jpeg", "image/png", "image/webp"].includes(file.type) &&
		!/\.(pdf|jpe?g|png|webp)$/i.test(file.name)
	) {
		event.target.value = "";
		row.attachment = null;
		actionError.value = __(
			"Unsupported file type. Upload a PDF, JPG, PNG, or WebP file.",
		);
		return;
	}
	row.attachment = file;
	row.attachment_uploaded = false;
	actionError.value = "";
}
function costDescription(row) {
	return [
		__(row.cost_type),
		row.supplier && `${__("Supplier / Payee")}: ${row.supplier}`,
		row.reference && `${__("Reference")}: ${row.reference}`,
		row.notes,
	]
		.filter(Boolean)
		.join(" · ");
}
async function submitCost() {
	if (busy.value) return;
	if (!costCreationResult.value) {
		if (!costForm.value.receipts.length)
			return void (actionError.value = __("Select at least one Purchase Receipt."));
		if (
			!costForm.value.rows.length ||
			costForm.value.rows.some((row) => Number(row.amount) <= 0 || !row.expense_account)
		)
			return void (actionError.value = __(
				"Enter a positive amount and expense account for every cost.",
			));
	}
	busy.value = "cost";
	actionError.value = "";
	try {
		if (!costCreationResult.value) {
			const payload = {
				posting_date: costForm.value.posting_date,
				allocation_basis: costForm.value.allocation_basis,
				purchase_receipts: costForm.value.receipts.map((receipt_document) => ({
					receipt_document,
				})),
				taxes: costForm.value.rows.map((row) => ({
					description: costDescription(row),
					expense_account: row.expense_account,
					amount: Number(row.amount),
					currency: "SAR",
					exchange_rate: 1,
				})),
			};
			costCreationResult.value = await call(
				"an_truck_portal.api.import_file.create_landed_cost_voucher",
				{
					vehicle_import_file: props.name,
					data: payload,
					submit_now: 1,
					idempotency_key: operationKey.value,
				},
				true,
			);
		}
		for (const [index, row] of costForm.value.rows.entries()) {
			if (!row.attachment || row.attachment_uploaded) continue;
			const savedRow = costCreationResult.value.cost_rows?.find(
				(entry) => Number(entry.idx) === index + 1,
			);
			if (!savedRow)
				throw Error(__("Unable to link the attachment to cost row {0}.", [index + 1]));
			try {
				await uploadFile(row.attachment, "Landed Cost Taxes and Charges", savedRow.name, {
					method: "an_truck_portal.api.import_file.upload_cost_attachment",
					fields: { vehicle_import_file: props.name },
				});
				row.attachment_uploaded = true;
			} catch (e) {
				throw Error(__("Could not upload the attachment for cost row {0}: {1}", [
					index + 1,
					e.message || __("common.unexpected"),
				]));
			}
		}
		const result = costCreationResult.value;
		costDialog.value?.close();
		notification.value = __("Operation completed successfully: {0}", [result.name || ""]);
		await load();
		costCreationResult.value = null;
	} catch (e) {
		actionError.value = e.message || __("Unable to complete the operation");
	} finally {
		busy.value = "";
	}
}

async function searchVin() {
	const vin = vinQuery.value.trim();
	if (!vin || vinSearching.value) return;
	vinSearching.value = true;
	vinResult.value = undefined;
	try {
		vinResult.value = await call("an_truck.portal_search.get_vin_summary", { vin });
		if (vinResult.value?.import_file === props.name) {
			highlightedVin.value = vinResult.value.vin;
			await nextTick();
			document
				.getElementById(`vehicle-${CSS.escape(vinResult.value.vin)}`)
				?.scrollIntoView({ behavior: "smooth", block: "center" });
		}
	} finally {
		vinSearching.value = false;
	}
}
function openVehicle(vehicle) {
	vehicleDrawer.value?.open(vehicle, false);
}
function editVehicle(vehicle) {
	vehicleDrawer.value?.open(vehicle, true);
}
async function vehicleSaved() {
	await load();
}

onMounted(load);
</script>

<template>
	<div class="page workspace-page">
		<div v-if="state === 'loading'" class="panel empty">{{ __("Loading…") }}</div>
		<div v-else-if="state === 'error'" class="panel empty error">
			{{ error }} <button class="button secondary" @click="load">{{ __("Retry") }}</button>
		</div>
		<template v-else>
			<section class="vin-lookup panel" aria-labelledby="vin-search-title">
				<div>
					<strong id="vin-search-title">{{ __("VIN Search") }}</strong
					><small>{{ __("Paste or scan a chassis number, then press Enter.") }}</small>
				</div>
				<form @submit.prevent="searchVin">
					<input
						v-model="vinQuery"
						class="ltr"
						:placeholder="__('Search by VIN...')"
						autocomplete="off"
					/><button class="button" :disabled="vinSearching">
						{{ vinSearching ? __("Searching…") : __("Search") }}
					</button>
				</form>
				<div v-if="vinResult === null" class="vin-result error">
					{{ __("No vehicle found for this VIN.") }}
				</div>
				<div v-else-if="vinResult" class="vin-result">
					<div>
						<bdi>{{ vinResult.vin }}</bdi
						><small
							>{{ vinResult.vehicle }} · {{ __(vinResult.vehicle_status) }}</small
						>
					</div>
					<div>
						<span>{{ __("Import File") }}: </span
						><router-link
							v-if="vinResult.import_file"
							:to="`/import-files/${encodeURIComponent(vinResult.import_file)}`"
							><bdi>{{ vinResult.import_file }}</bdi></router-link
						>
					</div>
					<button
						v-if="vinResult.import_file === name"
						class="text-button"
						@click="
							openVehicle(data.vehicles.find((row) => row.vin === vinResult.vin))
						"
					>
						{{ __("Open vehicle details") }}
					</button>
				</div>
			</section>

			<header class="workspace-header panel">
				<div class="workspace-title">
					<p class="eyebrow">{{ __("Vehicle Import File") }}</p>
					<h1>
						<bdi>{{ data.import_file.title || data.import_file.name }}</bdi>
					</h1>
					<p>
						<bdi>{{ data.import_file.name }}</bdi> · {{ data.import_file.supplier }}
					</p>
				</div>
				<div class="workspace-status">
					<span class="badge" :class="{ success: isCompleted }">{{
						__(data.import_file.status)
					}}</span
					><a
						v-if="permissions['Vehicle Import File']?.read"
						class="button secondary small"
						:href="desk('Vehicle Import File', name)"
						>{{ __("Open in Desk") }}</a
					><button
						v-if="canCloseFile"
						type="button"
						class="button small"
						:disabled="!!busy"
						@click="completeImportFile"
					>
						{{ busy === "close-file" ? __("Processing...") : __("Close File") }}
					</button
					>
				</div>
				<div class="workspace-metrics">
					<div>
						<small>{{ __("Purchase Status") }}</small
						><b>{{ __(summary.purchase_status) }}</b>
					</div>
					<div>
						<small>{{ __("Receiving Status") }}</small
						><b>{{ __(summary.receiving_status) }}</b>
					</div>
					<div>
						<small>{{ __("Number of Vehicles") }}</small
						><b>{{ summary.expected }}</b>
					</div>
					<div>
						<small>{{ __("Received Vehicles") }}</small
						><b>{{ summary.received }}</b>
					</div>
					<div>
						<small>{{ __("VINs Entered") }}</small
						><b>{{ summary.vins_entered }}</b>
					</div>
					<div>
						<small>{{ __("Purchase Value") }}</small
						><b>{{ amount(summary.purchase_value, summary.supplier_currency) }}</b>
					</div>
					<div>
						<small>{{ __("Additional Costs") }}</small
						><b>{{ amount(summary.additional_cost) }}</b>
					</div>
					<div>
						<small>{{ __("Last Update") }}</small
						><b>{{ date(summary.last_update) }}</b>
					</div>
				</div>
			</header>
			<p v-if="closeFileError" class="form-error" role="alert">
				{{ closeFileError }}
			</p>

			<section class="process panel" :aria-label="__('Process Status')">
				<div
					v-for="(step, index) in data.process"
					:key="step.key"
					class="process-step"
					:class="step.state"
				>
					<span>{{ index + 1 }}</span
					><b>{{ __(step.label) }}</b>
				</div>
			</section>

			<div class="action-strip" v-if="canCreatePO || canReceive || canAddCost">
				<button v-if="canCreatePO" class="button" @click="openPurchase">
					{{ __("Create Purchase Order") }}
				</button>
				<button v-if="canReceive" class="button" @click="openReceiving">
					{{ summary.received ? __("Receive Another Batch") : __("Receive Vehicles") }}
				</button>
				<button v-if="canAddCost" class="button secondary" @click="openCost">
					{{ __("Add Import Cost") }}
				</button>
			</div>

			<div class="workspace-grid">
				<section class="panel section-card purchase-card">
					<div class="section-head">
						<div>
							<p class="eyebrow">{{ __("Purchasing") }}</p>
							<h2>{{ __("Purchase Order") }}</h2>
						</div>
						<button v-if="canCreatePO" class="button small" @click="openPurchase">
							{{ __("Create Purchase Order") }}
						</button>
					</div>
					<div v-if="data.purchase.primary" class="compact-details">
						<div>
							<small>{{ __("PO Number") }}</small
							><router-link
								:to="{
									name: 'purchase-order-detail',
									params: { name: data.purchase.primary.name },
								}"
								><bdi>{{ data.purchase.primary.name }}</bdi></router-link
							>
						</div>
						<div>
							<small>{{ __("Supplier") }}</small
							><b>{{ data.purchase.primary.party }}</b>
						</div>
						<div>
							<small>{{ __("Date") }}</small
							><b>{{ date(data.purchase.primary.date) }}</b>
						</div>
						<div>
							<small>{{ __("Quantity") }}</small
							><b>{{ data.purchase.primary.total_qty }}</b>
						</div>
						<div>
							<small>{{ __("Total") }}</small
							><b>{{
								amount(
									data.purchase.primary.amount,
									data.purchase.primary.currency,
								)
							}}</b>
						</div>
						<div>
							<small>{{ __("Document Status") }}</small
							><span class="badge neutral">{{
								docStatus(data.purchase.primary)
							}}</span>
						</div>
					</div>
					<div v-else class="empty compact">
						{{ __("No Purchase Order has been created for this file.") }}
					</div>
				</section>

				<section class="panel section-card receiving-card">
					<div class="section-head">
						<div>
							<p class="eyebrow">{{ __("Receiving") }}</p>
							<h2>{{ __("Receive Vehicles") }}</h2>
						</div>
						<button v-if="canReceive" class="button small" @click="openReceiving">
							{{
								summary.received
									? __("Receive Another Batch")
									: __("Receive Vehicles")
							}}
						</button>
					</div>
					<div class="receipt-summary">
						<div>
							<strong>{{ summary.expected }}</strong
							><span>{{ __("Expected") }}</span>
						</div>
						<div>
							<strong>{{ summary.received }}</strong
							><span>{{ __("Received") }}</span>
						</div>
						<div>
							<strong>{{ summary.remaining }}</strong
							><span>{{ __("Remaining") }}</span>
						</div>
					</div>
					<p v-if="!canReceive" class="muted">
						{{
							__("A submitted Purchase Order with a remaining quantity is required.")
						}}
					</p>
				</section>
			</div>

			<section class="panel section-card vehicles-section">
				<div class="section-head">
					<div>
						<p class="eyebrow">{{ __("Vehicles / VIN") }}</p>
						<h2>{{ __("Vehicles in this Import File") }}</h2>
					</div>
					<span class="badge neutral">{{ data.vehicles.length }}</span>
				</div>
				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>{{ __("VIN") }}</th>
								<th>{{ __("Vehicle / Item") }}</th>
								<th>{{ __("Model") }}</th>
								<th>{{ __("Color") }}</th>
								<th>{{ __("Landed Cost") }}</th>
								<th>{{ __("Sales Status") }}</th>
								<th>{{ __("Actions") }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-if="!data.vehicles.length">
								<td colspan="7" class="empty compact">
									{{ __("No vehicles have been received yet.") }}
								</td>
							</tr>
							<tr
								v-for="vehicle in data.vehicles"
								:id="`vehicle-${vehicle.vin}`"
								:key="vehicle.name"
								:class="{ highlighted: highlightedVin === vehicle.vin }"
							>
								<td>
									<button class="link-button ltr" @click="openVehicle(vehicle)">
										{{ vehicle.vin }}
									</button>
								</td>
								<td>{{ vehicle.item_name || vehicle.item_code }}</td>
								<td>{{ vehicle.model || "—" }}</td>
								<td>{{ vehicle.color || "—" }}</td>
								<td>
									{{
										amount(vehicle.final_valuation_rate, vehicle.cost_currency)
									}}
								</td>
								<td>{{ __(vehicle.sales_status) }}</td>
								<td class="row-actions">
									<button class="text-button" @click="openVehicle(vehicle)">
										{{ __("View") }}
									</button>
									<button
										v-if="!isCompleted && permissions['Vehicle Master']?.write"
										class="text-button"
										@click="editVehicle(vehicle)"
									>
										{{ __("Edit") }}
									</button>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<section class="panel section-card costs-section">
				<div class="section-head">
					<div>
						<p class="eyebrow">{{ __("Costing") }}</p>
						<h2>{{ __("Import Costs") }}</h2>
					</div>
					<button v-if="canAddCost" class="button small" @click="openCost">
						{{ __("+ Add Cost") }}
					</button>
				</div>
				<div class="cost-totals">
					<div>
						<small>{{ __("Purchase Cost") }}</small
						><strong>{{
							amount(summary.purchase_value, summary.supplier_currency)
						}}</strong>
					</div>
					<div>
						<small>{{ __("Total Additional Costs") }}</small
						><strong>{{ amount(data.costs.total, data.costs.currency) }}</strong>
					</div>
					<div>
						<small>{{ __("Landed Cost") }}</small
						><strong>{{ amount(summary.final_valuation) }}</strong>
					</div>
				</div>
				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>{{ __("Cost Type") }}</th>
								<th>{{ __("Expense Account") }}</th>
								<th>{{ __("Amount") }}</th>
								<th>{{ __("Currency") }}</th>
								<th>{{ __("Date") }}</th>
								<th>{{ __("Reference") }}</th>
								<th>{{ __("Attachment") }}</th>
								<th>{{ __("Document Status") }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-if="!data.costs.rows.length">
								<td colspan="8" class="empty compact">
									{{ __("No import costs have been added yet.") }}
								</td>
							</tr>
							<tr v-for="row in data.costs.rows" :key="`${row.voucher}-${row.idx}`">
								<td>{{ row.description }}</td>
								<td>{{ row.expense_account }}</td>
								<td>{{ amount(row.amount, row.account_currency) }}</td>
								<td>{{ row.account_currency }}</td>
								<td>{{ date(row.date) }}</td>
								<td>
									<router-link :to="{ name: 'landed-cost-detail', params: { name: row.voucher } }"
										><bdi>{{ row.voucher }}</bdi></router-link
									>
								</td>
								<td>
									<div v-if="row.attachments?.length" class="attachment-links">
										<a
											v-for="file in row.attachments"
											:key="file.name"
											:href="file.file_url"
											target="_blank"
											rel="noopener"
											>{{ file.file_name }}</a
										>
									</div>
									<span v-else>—</span>
								</td>
								<td>{{ docStatus(row) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<div class="workspace-grid lower-grid">
				<section class="panel section-card">
					<div class="section-head">
						<h2>{{ __("Related Documents") }}</h2>
					</div>
					<div class="document-list">
						<template v-for="(rows, group) in data.documents" :key="group"
							><div v-for="row in rows" :key="`${group}-${row.name}`">
								<span>{{ __(documentDoctype(group)) }}</span
								><router-link
									v-if="documentRoute(group, row.name)"
									:to="documentRoute(group, row.name)"
									><bdi>{{ row.name }}</bdi></router-link
								><a v-else :href="desk(documentDoctype(group), row.name)"
									><bdi>{{ row.name }}</bdi></a
								><small>{{ docStatus(row) }}</small>
							</div></template
						>
					</div>
				</section>
				<section class="panel section-card">
					<div class="section-head">
						<h2>{{ __("Activity") }}</h2>
					</div>
					<ol class="timeline">
						<li v-for="row in data.activity" :key="`${row.type}-${row.document}`">
							<span></span>
							<div>
								<b>{{ __(row.label) }}</b
								><small
									><bdi>{{ row.document }}</bdi> ·
									{{ date(row.timestamp) }}</small
								>
							</div>
						</li>
					</ol>
				</section>
			</div>
		</template>

		<VehicleDrawer ref="vehicleDrawer" @saved="vehicleSaved" />

		<PurchaseOrderDialog
			ref="purchaseDialog"
			:vehicle-import-file="name"
			:supplier="data.import_file?.supplier"
			:currency="data.import_file?.supplier_currency"
			@created="load"
		/>
		<dialog
			ref="receivingDialog"
			class="operation-dialog wide-dialog"
			:aria-label="__('Receive Vehicles')"
			@cancel.prevent="close(receivingDialog)"
		>
			<form @submit.prevent="submitReceipt">
				<div class="dialog-head">
					<div>
						<p class="eyebrow">{{ __("Receiving") }}</p>
						<h2>{{ __("Receive Vehicles") }}</h2>
					</div>
					<button
						type="button"
						class="icon"
						:aria-label="__('Close')"
						@click="close(receivingDialog)"
					>
						×
					</button>
				</div>
				<div class="dialog-body">
					<div class="form-grid">
						<label
							><span>{{ __("Purchase Order") }}</span
							><select
								v-model="receiptForm.purchase_order"
								required
								@change="changeReceiptPO"
							>
								<option
									v-for="po in data.receiving?.purchase_orders"
									:value="po.name"
								>
									{{ po.name }}
								</option>
							</select></label
						><label
							><span>{{ __("Posting Date") }}</span
							><input v-model="receiptForm.posting_date" type="date" required
						/></label>
					</div>
					<h3>{{ __("Expected Vehicles / Items") }}</h3>
					<div class="table-wrap">
						<table class="input-table">
							<thead>
								<tr>
									<th>{{ __("Item") }}</th>
									<th>{{ __("Description") }}</th>
									<th>{{ __("Ordered Qty") }}</th>
									<th>{{ __("Previously Received") }}</th>
									<th>{{ __("Remaining Qty") }}</th>
									<th>{{ __("Receive Qty") }}</th>
									<th>{{ __("Warehouse") }}</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="row in receiptForm.items"
									:key="row.purchase_order_item"
								>
									<td>
										<bdi>{{ row.item_code }}</bdi>
									</td>
									<td>{{ row.item_name }}</td>
									<td>{{ row.ordered_qty }}</td>
									<td>{{ row.received_qty }}</td>
									<td>{{ row.remaining_qty }}</td>
									<td>
										<input
											v-model.number="row.qty"
											type="number"
											min="0"
											:max="row.remaining_qty"
											step="1"
											@change="syncVins"
										/>
									</td>
									<td>
										<input v-model="row.warehouse" list="warehouse-options" />
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div v-if="receiptForm.vins.length" class="vin-entry">
						<div class="dialog-section-head">
							<div>
								<h3>{{ __("VIN / Chassis Entry") }}</h3>
								<p>
									{{
										__(
											"Scan or type each VIN. Press Enter to move to the next row.",
										)
									}}
								</p>
							</div>
							<span class="badge neutral"
								>{{ receiptForm.vins.filter((row) => row.vin).length }} /
								{{ receiptForm.vins.length }}</span
							>
						</div>
						<div class="vin-grid">
							<label
								v-for="(row, index) in receiptForm.vins"
								:key="`${row.purchase_order_item}-${index}`"
								><span
									>{{ __("Vehicle {0}", [index + 1]) }} ·
									<bdi>{{ row.item_code }}</bdi></span
								><input
									v-model.trim="row.vin"
									class="ltr"
									:data-vin-index="index"
									autocomplete="off"
									required
									@keydown.enter.prevent="nextVin(index)"
							/></label>
						</div>
					</div>
					<p v-if="actionError" class="form-error">{{ actionError }}</p>
				</div>
				<div class="dialog-actions">
					<button
						type="button"
						class="button secondary"
						:disabled="!!busy"
						@click="close(receivingDialog)"
					>
						{{ __("Cancel") }}</button
					><button class="button" :disabled="!!busy">
						{{ busy === "receipt" ? __("Processing...") : __("Submit Receipt") }}
					</button>
				</div>
			</form>
		</dialog>

		<dialog
			ref="costDialog"
			class="operation-dialog wide-dialog"
			:aria-label="__('Add Import Cost')"
			@cancel.prevent="close(costDialog)"
		>
			<form @submit.prevent="submitCost">
				<div class="dialog-head">
					<div>
						<p class="eyebrow">{{ __("Costing") }}</p>
						<h2>{{ __("Add Import Cost") }}</h2>
					</div>
					<button
						type="button"
						class="icon"
						:aria-label="__('Close')"
						@click="close(costDialog)"
					>
						×
					</button>
				</div>
				<div class="dialog-body">
					<div class="form-grid">
						<label
							><span>{{ __("Date") }}</span
							><input v-model="costForm.posting_date" type="date" required /></label
						><label
							><span>{{ __("Allocation Basis") }}</span
							><select v-model="costForm.allocation_basis">
								<option value="Qty">{{ __("Quantity") }}</option>
								<option value="Amount">{{ __("Amount") }}</option>
							</select></label
						>
					</div>
					<fieldset>
						<legend>{{ __("Purchase Receipts") }}</legend>
						<label v-for="receipt in submittedReceipts" class="check-row"
							><input
								v-model="costForm.receipts"
								type="checkbox"
								:value="receipt.name"
							/><bdi>{{ receipt.name }}</bdi></label
						>
					</fieldset>
					<div class="dialog-section-head">
						<h3>{{ __("Additional Costs") }}</h3>
						<button
							type="button"
							class="button secondary small"
							:disabled="!!busy || !!costCreationResult"
							@click="addCostRow"
						>
							{{ __("+ Add Cost") }}
						</button>
					</div>
					<div class="editable-grid cost-rows">
						<div
							v-for="(row, index) in costForm.rows"
							:key="index"
							class="cost-edit-row"
						>
							<label
								><span>{{ __("Cost Type") }}</span
								><select v-model="row.cost_type">
									<option
										v-for="type in [
											'Customs',
											'Shipping',
											'Port Charges',
											'Clearance',
											'Insurance',
											'Transportation',
											'Inspection',
											'Other Direct Costs',
										]"
										:value="type"
									>
										{{ __(type) }}
									</option>
								</select></label
							><label
								><span>{{ __("Supplier / Payee") }}</span
								><input v-model="row.supplier" /></label
							><label
								><span>{{ __("Amount") }}</span
								><input
									v-model.number="row.amount"
									type="number"
									min="0.01"
									step="any"
									required /></label
							><label
								><span>{{ __("Expense Account") }}</span
								><input
									v-model="row.expense_account"
									list="expense-options"
									required /></label
							><label
								><span>{{ __("Reference") }}</span
								><input v-model="row.reference" /></label
							><label
								><span>{{ __("Notes") }}</span
								><input v-model="row.notes" /></label
							><label class="cost-attachment"
								><span>{{ __("Attachment") }}</span
								><input
									type="file"
									accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
									@change="selectCostAttachment(row, $event)" />
								<small>{{ __("Supported files: PDF, JPG, PNG, WebP") }}</small></label
							><button
								type="button"
								class="remove-row"
								:disabled="!!busy || !!costCreationResult"
								:aria-label="__('Delete')"
								@click="costForm.rows.splice(index, 1)"
							>
								×
							</button>
						</div>
					</div>
					<datalist id="expense-options">
						<option
							v-for="account in options?.expense_accounts"
							:value="account.name"
						></option>
					</datalist>
					<p class="field-help">
						{{
							__(
								"Supplier, reference and notes are stored in the standard Landed Cost row description because ERPNext has no separate fields for them.",
							)
						}}
					</p>
					<p v-if="actionError" class="form-error">{{ actionError }}</p>
				</div>
				<div class="dialog-actions">
					<button
						type="button"
						class="button secondary"
						:disabled="!!busy"
						@click="close(costDialog)"
					>
						{{ __("Cancel") }}</button
					><button class="button" :disabled="!!busy">
						{{ busy === "cost" ? __("Processing...") : __("Create and Submit") }}
					</button>
				</div>
			</form>
		</dialog>
		<ConfirmDialog
			ref="closeFileConfirm"
			title="Close Vehicle Import File"
			message="This file will be marked as completed and no further changes will be allowed through AN Truck Portal."
			cancel-label="Cancel"
			confirm-label="Close File"
		/>
	</div>
</template>
