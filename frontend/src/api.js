import { reactive } from "vue";
import { __, language } from "./i18n";
export { __ } from "./i18n";
export const boot = window.anTruckBoot || {};
export const session = reactive({ ended: false });
async function readResponse(response) {
	let payload = {};
	try {
		payload = await response.json();
	} catch {}
	if (response.status === 401) {
		session.ended = true;
		throw Error(__("Your session has ended."));
	}
	if (!response.ok || payload.exc) {
		let message = __("common.unexpected");
		if (
			response.status < 500 ||
			[
				"ValidationError",
				"MandatoryError",
				"LinkValidationError",
				"DuplicateEntryError",
				"PermissionError",
				"TimestampMismatchError",
			].includes(payload.exc_type)
		) {
			try {
				const messages = JSON.parse(payload._server_messages || "[]");
				message =
					messages
						.map((value) => __(JSON.parse(value).message.replace(/<[^>]*>/g, "")))
						.join(" ") || message;
			} catch {}
		}
		throw Error(message);
	}
	return payload.message;
}

export async function call(method, args = {}, write = false) {
	const url = new URL(`/api/method/${method}`, location.origin);
	if (!write)
		Object.entries(args).forEach(([key, value]) => {
			if (value !== "" && value != null)
				url.searchParams.set(
					key,
					typeof value === "object" ? JSON.stringify(value) : value,
				);
		});
	url.searchParams.set("_lang", language.value);
	const response = await fetch(url, {
		method: write ? "POST" : "GET",
		credentials: "same-origin",
		headers: {
			Accept: "application/json",
			...(write
				? { "Content-Type": "application/json", "X-Frappe-CSRF-Token": boot.csrf_token }
				: {}),
		},
		...(write ? { body: JSON.stringify(args) } : {}),
	});
	return readResponse(response);
}

export async function uploadFile(file, doctype, docname, options = {}) {
	const url = new URL(`/api/method/${options.method || "upload_file"}`, location.origin);
	url.searchParams.set("_lang", language.value);
	const body = new FormData();
	body.append("file", file, file.name);
	body.append("doctype", doctype);
	body.append("docname", docname);
	body.append("is_private", "1");
	Object.entries(options.fields || {}).forEach(([key, value]) => body.append(key, value));
	const response = await fetch(url, {
		method: "POST",
		credentials: "same-origin",
		headers: {
			Accept: "application/json",
			"X-Frappe-CSRF-Token": boot.csrf_token,
		},
		body,
	});
	return readResponse(response);
}
