# -*- coding: utf-8 -*-
import re

from odoo import models

NAVY = "#1F3864"
TOTAL_FILL = "#9BC2E6"
# Anchos de columna (caracteres), en el orden de NOMINA_COLUMNS.
WIDTHS = {
    "n": 4, "codigo": 6, "nombre": 34, "puesto": 12, "ingreso": 9,
    "horas_extra": 7,
}
MONEY_WIDTH = 10.5
# Columnas donde un cero se muestra como "-" (como en la hoja del cliente);
# en el resto, el cero queda en blanco.
DASH_ON_ZERO = ("total_horas_extra", "primera_quincena")
# Firmas: (primera columna, última columna) en índices 0-based.
SIGN_PREPARED = (4, 8)
SIGN_APPROVED = (13, 16)


class NominaXlsx(models.AbstractModel):
    """Nómina de sueldos y salarios en Excel, con el formato del cliente (una
    hoja por lote). Los datos son los mismos del PDF:
    hr.payslip.run._l10n_gt_nomina_rows()."""

    _name = "report.l10n_gt_payroll_report_xlsx.nomina_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Nómina de sueldos y salarios (Excel)"

    def _formats(self, workbook):
        base = {"font_name": "Arial", "font_size": 8, "valign": "vcenter"}
        cell = dict(base, border=1, border_color="#BFBFBF")
        f = {
            "company": workbook.add_format(dict(base, font_size=14, align="center")),
            "subtitle": workbook.add_format(dict(base, font_size=9, align="center")),
            "header": workbook.add_format(dict(
                base, bold=True, font_color="#FFFFFF", bg_color=NAVY, border=1,
                border_color="#FFFFFF", align="center", text_wrap=True)),
            "text": workbook.add_format(cell),
            "int": workbook.add_format(dict(cell, align="right")),
            "date": workbook.add_format(dict(cell, num_format="d/mm/yy", align="right")),
            "hours": workbook.add_format(dict(cell, num_format="#,##0.00;-#,##0.00;;@")),
            "money": workbook.add_format(dict(cell, num_format="#,##0.00;-#,##0.00;;@")),
            "money_dash": workbook.add_format(dict(
                cell, num_format='#,##0.00;-#,##0.00;"-";@')),
            "total": workbook.add_format(dict(
                base, bold=True, num_format="#,##0.00;-#,##0.00;-", bg_color=TOTAL_FILL,
                top=6, bottom=1)),
            "total_blank": workbook.add_format(dict(base, top=6)),
            "sign_line": workbook.add_format(dict(base, align="center", top=1)),
            "sign_name": workbook.add_format(dict(base, align="center")),
        }
        return f

    def _sheet_name(self, run, used):
        name = re.sub(r"[\[\]:*?/\\]", " ", run.name or "Nomina").strip()[:31] or "Nomina"
        candidate, n = name, 2
        while candidate in used:
            suffix = " (%d)" % n
            candidate = name[:31 - len(suffix)] + suffix
            n += 1
        used.add(candidate)
        return candidate

    def generate_xlsx_report(self, workbook, data, runs):
        fmt = self._formats(workbook)
        used = set()
        for run in runs:
            self._write_run(workbook, fmt, run, self._sheet_name(run, used))

    def _write_run(self, workbook, fmt, run, sheet_name):
        cols = run.NOMINA_COLUMNS
        last = len(cols) - 1
        rows = run._l10n_gt_nomina_rows()
        totals = run._l10n_gt_nomina_totals(rows)
        company = run.company_id

        sheet = workbook.add_worksheet(sheet_name)
        sheet.set_landscape()
        sheet.set_paper(5)  # Legal (oficio)
        sheet.fit_to_pages(1, 0)
        sheet.set_margins(left=0.25, right=0.25, top=0.4, bottom=0.4)
        sheet.repeat_rows(3)
        sheet.hide_gridlines(2)
        for idx, (key, _h, is_money, _t) in enumerate(cols):
            sheet.set_column(idx, idx, WIDTHS.get(key, MONEY_WIDTH if is_money else 10))

        # Encabezado
        sheet.merge_range(0, 0, 0, last, company.name or "", fmt["company"])
        sheet.merge_range(1, 0, 1, last, "NÓMINA DE SUELDOS Y SALARIOS", fmt["subtitle"])
        sheet.merge_range(2, 0, 2, last, run._l10n_gt_nomina_period_label(), fmt["subtitle"])
        sheet.set_row(3, 30)
        for idx, (_k, header, _m, _t) in enumerate(cols):
            sheet.write(3, idx, header, fmt["header"])
        sheet.freeze_panes(4, 3)

        # Filas
        r = 4
        for row in rows:
            for idx, (key, _h, is_money, _t) in enumerate(cols):
                value = row[key]
                if key == "ingreso":
                    if value:
                        sheet.write_datetime(r, idx, value, fmt["date"])
                    else:
                        sheet.write_blank(r, idx, None, fmt["date"])
                elif key == "n":
                    sheet.write_number(r, idx, value, fmt["int"])
                elif key == "horas_extra":
                    sheet.write_number(r, idx, value or 0.0, fmt["hours"])
                elif is_money:
                    sheet.write_number(r, idx, round(value or 0.0, 2),
                                       fmt["money_dash" if key in DASH_ON_ZERO else "money"])
                else:
                    sheet.write_string(r, idx, str(value or ""), fmt["text"])
            r += 1

        # Totales
        for idx, (key, _h, _m, with_total) in enumerate(cols):
            if with_total:
                sheet.write_number(r, idx, round(totals[key], 2), fmt["total"])
            else:
                sheet.write_blank(r, idx, None, fmt["total_blank"])

        # Firmas
        r += 4
        for (c1, c2), label, name in (
                (SIGN_PREPARED, "Elaborado por:", company.l10n_gt_payroll_prepared_by),
                (SIGN_APPROVED, "Aprobado por:", company.l10n_gt_payroll_approved_by)):
            sheet.merge_range(r, c1, r, c2, label, fmt["sign_line"])
            sheet.merge_range(r + 1, c1, r + 1, c2, name or "", fmt["sign_name"])
