<script setup>
defineProps({ columns: Array, rows: Array, caption: String });
</script>
<template>
	<div class="table-wrap" tabindex="0" :aria-label="caption">
		<table>
			<caption class="sr-only">
				{{
					caption
				}}
			</caption>
			<thead>
				<tr>
					<th v-for="column in columns" :key="column.key" scope="col">
						{{ column.label }}
					</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="row in rows" :key="row.name">
					<td v-for="column in columns" :key="column.key">
						<slot :name="column.key" :row="row"
							><span :class="{ 'ltr-value': column.ltr }">{{
								row[column.key] || "—"
							}}</span></slot
						>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>
