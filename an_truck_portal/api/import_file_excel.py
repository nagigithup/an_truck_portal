"""Permission-checked XLSX I/O for import-file masters, never financial documents."""
import base64
import json
from io import BytesIO
from zipfile import ZipFile

import frappe
from frappe import _

from an_truck_portal.access import require_read
from an_truck_portal.import_file_metrics import COLUMNS

DT = "Vehicle Import File"
FIELDS = {"import_title":"Name", "supplier":"Supplier", "country_of_origin":"Country of Origin",
	"supplier_currency":"Supplier Currency", "total_expected_vehicles":"Expected Vehicles",
	"transaction_exchange_rate":"Exchange Rate", "notes":"Notes"}
MAX_ROWS = 1000


def _label(key,language=None):
	from pathlib import Path
	lang = language or ("ar" if frappe.local.lang=="ar" else "en")
	messages = frappe.flags.get('import_excel_messages_'+lang)
	if messages is None:
		path=Path(frappe.get_app_path('an_truck_portal','..','frontend','src','locales',lang+'.json'))
		messages=json.loads(path.read_text())
		frappe.flags['import_excel_messages_'+lang]=messages
	return messages.get(key) or _(key)


def _create_access(company):
	require_read(DT)
	if not frappe.has_permission(DT,"create"):
		frappe.throw(_("Not permitted"),frappe.PermissionError)
	if not company:
		frappe.throw(_("Select a company before importing."))
	co = frappe.get_doc("Company",company)
	co.check_permission("read")
	return co


def _download(data,filename,rtl=False,text_identifiers=False):
	from frappe.utils.xlsxutils import make_xlsx
	import xlsxwriter
	stream = BytesIO()
	wb = xlsxwriter.Workbook(stream,{"constant_memory":True,"strings_to_formulas":False,"strings_to_urls":False})
	# Use the standard Frappe Unicode/formula-safe writer.
	make_xlsx(data,_("Vehicle Import File"),wb=wb,column_widths=[28]*len(data[0]))
	ws = wb.worksheets()[0]
	if text_identifiers:
		ws.set_column(0,1,28,wb.add_format({'num_format':'@'}))
	ws.freeze_panes(1,0)
	ws.autofilter(0,0,max(0,len(data)-1),len(data[0])-1)
	if rtl: ws.right_to_left()
	wb.close()
	frappe.local.response.update({"type":"download","filename":filename+".xlsx","filecontent":stream.getvalue(),
		"content_type":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","display_content_as":"attachment"})


@frappe.whitelist(methods=["GET"])
def template(company):
	_create_access(company)
	_download([[_label(label) for label in FIELDS.values()]],"import-files-template",frappe.local.lang=="ar",text_identifiers=True)


@frappe.whitelist(methods=["GET"])
def export(company=None,search=None,filters=None):
	require_read(DT)
	if not frappe.has_permission(DT,"export"):
		frappe.throw(_("Not permitted"),frappe.PermissionError)
	from an_truck_portal.api.records import list_records
	output = [[_label(label) for label in COLUMNS.values()]]
	page, seen = 1,set()
	while True:
		result = list_records(DT,company=company,search=search,filters=filters,page=page,page_length=100)
		if result['total']>20000:
			frappe.throw(_("Too many rows. Narrow the export filters."))
		for row in result['rows']:
			if row.name in seen: continue
			seen.add(row.name)
			values = []
			for field in COLUMNS:
				value = row.get(field)
				if field in {"purchase_value","paid_amount","outstanding_amount"}:
					value = "\n".join(f"{entry['amount']} {entry['currency']}" for entry in value) if value is not None else "—"
				elif field=="status" and value:
					value = _label(value)
				values.append(value if value is not None else "—")
			output.append(values)
		if not result['has_more']: break
		page += 1
	_download(output,"import-files",frappe.local.lang=="ar")


def _parse(content):
	from openpyxl import load_workbook
	try:
		if not isinstance(content,str) or len(content)>4*((2*1024*1024+2)//3): raise ValueError
		binary = base64.b64decode(content,validate=True)
		if len(binary)>2*1024*1024: raise ValueError
		with ZipFile(BytesIO(binary)) as archive:
			if sum(f.file_size for f in archive.infolist())>20*1024*1024: raise ValueError
		book = load_workbook(BytesIO(binary),read_only=True,data_only=False)
	except Exception:
		frappe.throw(_("Upload a valid XLSX workbook within the size limit."))
	try:
		ws = book.active
		if (ws.max_row or 0)>MAX_ROWS+1: frappe.throw(_("The import template supports at most 1000 rows."))
		if (ws.max_column or 0)>len(FIELDS): frappe.throw(_("Use the downloaded import template without changing its columns."))
		data = list(ws.iter_rows(max_row=min(ws.max_row or MAX_ROWS+2,MAX_ROWS+2),max_col=ws.max_column or len(FIELDS)))
		if not data: frappe.throw(_("The workbook is empty."))
		from frappe.translate import get_all_translations
		arabic = get_all_translations("ar")
		aliases = {name:name for name in FIELDS}
		for name,label in FIELDS.items():
			aliases[label]=name
			aliases[arabic.get(label,label)]=name
			aliases[_label(label,'ar')]=name
			aliases[_label(label,'en')]=name
		headers = [aliases.get(str(cell.value or '').strip()) for cell in data[0]]
		if None in headers or len(set(headers))!=len(headers) or not {'import_title','supplier'}<=set(headers):
			frappe.throw(_("Use the downloaded import template without changing its columns."))
		result=[]
		for index,cells in enumerate(data[1:],2):
			if not any(c.value is not None for c in cells):continue
			if index>MAX_ROWS+1:frappe.throw(_("The import template supports at most 1000 rows."))
			if any(c.data_type=='f' for c in cells):
				result.append((index,None,_("Formulas are not allowed in import rows.")));continue
			values={name:cells[i].value for i,name in enumerate(headers) if i<len(cells) and cells[i].value is not None}
			if any(isinstance(values.get(key),(int,float)) for key in ('import_title','supplier')):
				result.append((index,None,_("Use text cells for names and supplier codes.")));continue
			result.append((index,values,None))
		if not result:frappe.throw(_("The workbook is empty."))
		return result
	finally:
		book.close()


def _document(values,company):
	values = {key:value.strip() if isinstance(value,str) else value for key,value in values.items()}
	if not values.get('import_title') or not values.get('supplier'):
		frappe.throw(_("Name and Supplier are required."))
	supplier = frappe.get_doc('Supplier',values['supplier'])
	supplier.check_permission('read')
	if supplier.disabled: frappe.throw(_("Select an enabled supplier."))
	values['supplier_currency'] = values.get('supplier_currency') or supplier.default_currency or company.default_currency
	for field in ('total_expected_vehicles','transaction_exchange_rate'):
		if field in values:
			try:
				import math
				if not math.isfinite(float(values[field])):raise ValueError
			except (TypeError,ValueError): frappe.throw(_("Enter valid numeric quantities and exchange rates."))
	doc=frappe.new_doc(DT)
	doc.update({'company':company.name,**values})
	doc._action='save'
	doc.check_permission('create')
	# Reuse this DocType's standard currency/quantity rules without preview writes.
	doc.run_method('before_validate')
	doc.run_method('validate')
	doc._validate_mandatory()
	doc._validate_links()
	return doc


@frappe.whitelist(methods=["POST"])
def import_rows(company,content,operation="validate",duplicates="skip"):
	co = _create_access(company)
	if operation not in {'validate','import'} or duplicates not in {'skip','error'}:
		frappe.throw(_("Invalid import options."))
	parsed = _parse(content)
	report, documents, seen = [],[],set()
	for index,values,error in parsed:
		entry={'row':index,'name':str((values or {}).get('import_title') or ''),'status':'valid','message':''}
		try:
			if error: frappe.throw(error)
			name = str(values.get('import_title') or '').strip()
			if name in seen or frappe.db.exists(DT,name):
				entry.update(status='skipped' if duplicates=='skip' else 'error',message=_("Duplicate name; existing records are never updated."))
			else:
				doc=_document(values,co)
				doc.name=name
				doc._validate()
				documents.append((doc,entry))
			seen.add(name)
		except (frappe.ValidationError,frappe.PermissionError,frappe.DoesNotExistError,ValueError,TypeError) as exc:
			from frappe.utils import strip_html
			entry.update(status='error',message=strip_html(str(exc)))
		report.append(entry)
	errors = any(row['status']=='error' for row in report)
	if operation=='import' and not errors:
		frappe.db.savepoint('import_file_excel')
		try:
			for doc,entry in documents:
				doc.insert()
				entry['status']='created'
		except Exception as exc:
			frappe.db.rollback(save_point='import_file_excel')
			for row in report:
				if row['status']=='created':row['status']='valid'
			from frappe.utils import strip_html
			entry.update(status='error',message=strip_html(str(exc)) if isinstance(exc,(frappe.ValidationError,frappe.PermissionError)) else _("Import failed. No rows were created."))
	return {'rows':report,'can_import':operation=='validate' and bool(documents) and not errors,'created':sum(r['status']=='created' for r in report)}
