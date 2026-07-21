# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrContract(models.Model):
    """Información salarial guatemalteca del contrato (§3.1.3, §4.1.4).

    Nota Odoo 18: el historial de contratos (§3.1.6) se obtiene del versionado
    nativo de hr.contract + el tracking de mail.thread sobre los campos salariales.
    """

    _inherit = "hr.contract"

    l10n_gt_salary_type = fields.Selection(
        selection=[
            ("monthly", "Mensual"),
            ("daily", "Diario"),
            ("hourly", "Por hora"),
        ],
        string="Tipo de salario",
        default="monthly",
        tracking=True,
    )
    l10n_gt_bonif_incentivo = fields.Monetary(
        "Bonificación Incentivo",
        default=250.0,
        tracking=True,
        help="Bonificación Incentivo pactada (Decreto 78-89 / 37-2001). "
             "Mínimo legal Q250.00. No forma parte del salario ordinario.",
    )
    l10n_gt_economic_zone_id = fields.Many2one(
        "l10n.gt.economic.zone",
        string="Circunscripción económica",
        tracking=True,
    )
    l10n_gt_exclude_overtime = fields.Boolean(
        "Excluir de horas extra",
        help="Puestos/empleados excluidos del cálculo de horas extra (§4.3.4).",
    )
    l10n_gt_contract_pdf = fields.Binary("Contrato firmado (PDF)", attachment=True)
    l10n_gt_contract_pdf_name = fields.Char("Nombre del archivo")

    def _l10n_gt_daily_wage(self):
        """Salario diario base para cálculos proporcionales (§4.1.2)."""
        self.ensure_one()
        return self.wage / 30.0

    @api.constrains("wage", "l10n_gt_economic_zone_id", "date_start")
    def _check_minimum_wage(self):
        """El salario ordinario no puede ser inferior al mínimo vigente (§4.1.4)."""
        for contract in self.filtered("l10n_gt_economic_zone_id"):
            minimum = contract.l10n_gt_economic_zone_id.get_minimum_wage(
                contract.date_start or fields.Date.today()
            )
            if minimum and contract.wage < minimum:
                raise ValidationError(
                    "El salario (Q%.2f) es inferior al salario mínimo vigente "
                    "(Q%.2f) para la circunscripción '%s'." % (
                        contract.wage, minimum,
                        contract.l10n_gt_economic_zone_id.name,
                    )
                )

    @api.constrains("l10n_gt_bonif_incentivo", "wage")
    def _check_bonif_incentivo(self):
        """Bonif. Incentivo no debe superar el salario ordinario (§4.2.4)."""
        for contract in self:
            if contract.l10n_gt_bonif_incentivo > contract.wage:
                raise ValidationError(
                    "La Bonificación Incentivo no puede ser superior al salario "
                    "ordinario (contrato de %s)." % contract.employee_id.name
                )
