# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nGtIsrProjection(models.Model):
    """Proyección anual del ISR asalariados (§4.10, anexo 8.5).

    Reproduce el cálculo: proyecta la renta afecta anual, resta la deducción
    personal (Q48,000), el IGSS anual y las deducciones comprobables, aplica los
    tramos (5% / 7% + Q15,000) y divide entre 12 la retención mensual.
    """

    _name = "l10n.gt.isr.projection"
    _description = "Proyección de ISR asalariados"
    _order = "year desc, employee_id"
    _rec_name = "display_name"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    year = fields.Integer(required=True, default=lambda s: fields.Date.today().year)
    company_id = fields.Many2one("res.company", default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda s: s.env.ref("base.GTQ", raise_if_not_found=False),
    )
    state = fields.Selection(
        selection=[("draft", "Borrador"), ("current", "Vigente")],
        default="draft",
        tracking=True,
    )
    line_ids = fields.One2many(
        "l10n.gt.isr.projection.line", "projection_id", string="Detalle mensual",
    )
    deduction_ids = fields.Many2many(
        "l10n.gt.isr.deduction",
        compute="_compute_deductions",
        string="Deducciones comprobables",
    )

    renta_bruta_anual = fields.Monetary(compute="_compute_amounts", store=True)
    renta_exenta = fields.Monetary(
        "Rentas exentas (Aguinaldo + Bono 14)", compute="_compute_amounts", store=True,
    )
    deduccion_personal = fields.Monetary(compute="_compute_amounts", store=True)
    igss_anual = fields.Monetary(compute="_compute_amounts", store=True)
    deducciones_comprobables = fields.Monetary(compute="_compute_amounts", store=True)
    renta_imponible = fields.Monetary(compute="_compute_amounts", store=True)
    isr_anual = fields.Monetary("ISR anual proyectado", compute="_compute_amounts", store=True)
    retencion_mensual = fields.Monetary(compute="_compute_amounts", store=True)

    _sql_constraints = [
        ("employee_year_uniq", "unique(employee_id, year, company_id)",
         "Ya existe una proyección de ISR para este empleado y año."),
    ]

    @api.depends("employee_id", "year")
    def _compute_deductions(self):
        for rec in self:
            rec.deduction_ids = self.env["l10n.gt.isr.deduction"].search([
                ("employee_id", "=", rec.employee_id.id),
                ("year", "=", rec.year),
            ])

    def _get_param(self, code):
        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            code, date(self.year or fields.Date.today().year, 12, 31)
        )

    def _isr_from_base(self, base):
        """Impuesto anual según tramos (§4.10.2)."""
        if base <= 0:
            return 0.0
        limite = self._get_param("l10n_gt_isr_tramo2_limite")
        if base <= limite:
            return base * self._get_param("l10n_gt_isr_tramo1_tasa")
        return (self._get_param("l10n_gt_isr_tramo2_fijo")
                + (base - limite) * self._get_param("l10n_gt_isr_tramo2_tasa"))

    @api.depends(
        "line_ids.sueldo_afecto", "line_ids.igss", "line_ids.aguinaldo",
        "line_ids.bono14", "deduction_ids.amount",
    )
    def _compute_amounts(self):
        for rec in self:
            rec.renta_bruta_anual = sum(rec.line_ids.mapped("sueldo_afecto"))
            rec.igss_anual = sum(rec.line_ids.mapped("igss"))
            rec.renta_exenta = (sum(rec.line_ids.mapped("aguinaldo"))
                                + sum(rec.line_ids.mapped("bono14")))
            rec.deduccion_personal = rec._get_param("l10n_gt_isr_deduccion_personal")
            rec.deducciones_comprobables = sum(rec.deduction_ids.mapped("amount"))
            rec.renta_imponible = max(0.0, (
                rec.renta_bruta_anual
                - rec.deduccion_personal
                - rec.igss_anual
                - rec.deducciones_comprobables
            ))
            rec.isr_anual = rec._isr_from_base(rec.renta_imponible)
            rec.retencion_mensual = rec.isr_anual / 12.0 if rec.isr_anual else 0.0

    # ------------------------------------------------------------------
    # Generación / recálculo de la proyección (§4.10.4)
    # ------------------------------------------------------------------
    def _populate_lines(self):
        """Construye las 12 líneas mensuales: real si hay nómina confirmada,
        proyectado con el salario vigente para los meses futuros."""
        self.ensure_one()
        self.line_ids.unlink()
        igss_tasa = self._get_param("l10n_gt_igss_laboral")
        contract = self.employee_id.contract_id
        wage = contract.wage if contract else 0.0
        Line = self.env["l10n.gt.isr.projection.line"]
        vals = []
        for month in range(1, 13):
            mfrom = date(self.year, month, 1)
            mto = date(self.year + (month // 12), (month % 12) + 1, 1) if month < 12 \
                else date(self.year, 12, 31)
            slips = self.env["hr.payslip"].search([
                ("employee_id", "=", self.employee_id.id),
                ("state", "=", "done"),
                ("date_from", "<=", mto),
                ("date_to", ">=", mfrom),
            ])
            if slips:
                afecto = sum(
                    l.total for s in slips for l in s.line_ids
                    if l.salary_rule_id.l10n_gt_afecto_isr
                )
                igss = -sum(
                    l.total for s in slips for l in s.line_ids if l.code == "IGSSLAB"
                )
            else:
                afecto = wage
                igss = wage * igss_tasa
            vals.append({
                "projection_id": self.id,
                "month": month,
                "sueldo_afecto": afecto,
                "igss": igss,
            })
        Line.create(vals)

    def action_generate(self):
        for rec in self:
            rec._populate_lines()
            # Solo una proyección vigente por empleado/año
            others = self.search([
                ("employee_id", "=", rec.employee_id.id),
                ("year", "=", rec.year),
                ("id", "!=", rec.id),
                ("state", "=", "current"),
            ])
            others.state = "draft"
            rec.state = "current"
        return True

    @api.model
    def _recompute_for(self, employee, year):
        """Recalcula (o crea) la proyección vigente de un empleado/año."""
        proj = self.search([
            ("employee_id", "=", employee.id), ("year", "=", year),
        ], limit=1)
        if not proj:
            proj = self.create({"employee_id": employee.id, "year": year})
        proj.action_generate()
        return proj

    @api.depends("employee_id", "year")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s - ISR %s" % (
                rec.employee_id.name or "", rec.year or "")


class L10nGtIsrProjectionLine(models.Model):
    _name = "l10n.gt.isr.projection.line"
    _description = "Detalle mensual de proyección ISR"
    _order = "projection_id, month"

    projection_id = fields.Many2one(
        "l10n.gt.isr.projection", required=True, ondelete="cascade",
    )
    currency_id = fields.Many2one(related="projection_id.currency_id")
    month = fields.Integer(required=True)
    month_name = fields.Char(compute="_compute_month_name")
    sueldo_afecto = fields.Monetary("Sueldo afecto")
    igss = fields.Monetary("IGSS laboral")
    aguinaldo = fields.Monetary("Aguinaldo (exento)")
    bono14 = fields.Monetary("Bono 14 (exento)")

    _MONTHS = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre",
        12: "Diciembre",
    }

    @api.depends("month")
    def _compute_month_name(self):
        for line in self:
            line.month_name = self._MONTHS.get(line.month, "")
