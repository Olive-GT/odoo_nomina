# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    """Datos guatemaltecos del empleado (§3.1 y §6.15 Informe del Empleador)."""

    _inherit = "hr.employee"

    # --- Identificación (§3.1.1) ---
    l10n_gt_dpi = fields.Char("DPI", groups="hr.group_hr_user", tracking=True)
    l10n_gt_nit = fields.Char("NIT", groups="hr.group_hr_user", tracking=True)

    # Nombres/apellidos separados (Informe del Empleador §6.15 los exige separados)
    l10n_gt_first_name = fields.Char("Primer nombre")
    l10n_gt_middle_name = fields.Char("Segundo nombre")
    l10n_gt_third_name = fields.Char("Tercer nombre")
    l10n_gt_first_surname = fields.Char("Primer apellido")
    l10n_gt_second_surname = fields.Char("Segundo apellido")
    l10n_gt_married_surname = fields.Char("Apellido de casada")

    # --- Información tributaria / IGSS (§3.1.4) ---
    l10n_gt_igss_applies = fields.Boolean("Afiliado al IGSS", default=True, tracking=True)
    l10n_gt_igss_affiliation = fields.Char("No. de afiliación IGSS", tracking=True)
    l10n_gt_isr_applies = fields.Boolean("Sujeto a ISR", default=True, tracking=True)

    # --- Datos para Informe del Empleador (§6.15) ---
    l10n_gt_children_count = fields.Integer("Cantidad de hijos")
    l10n_gt_profession = fields.Char("Título o diploma (profesión)")
    l10n_gt_academic_level = fields.Selection(
        selection=[
            ("2", "Primaria"),
            ("7", "Diversificado"),
            ("8", "Técnico / Universitario incompleto"),
            ("10", "Universitario / Licenciatura"),
            ("12", "Postgrado / Maestría"),
        ],
        string="Nivel académico (código MinTrab)",
    )
    l10n_gt_ethnic_group = fields.Selection(
        selection=[
            ("1", "Maya"),
            ("2", "Garífuna"),
            ("3", "Xinca"),
            ("4", "Ladino / Mestizo"),
            ("99", "No indica"),
        ],
        string="Pueblo de pertenencia (código MinTrab)",
        default="99",
    )
    l10n_gt_disability_type = fields.Selection(
        selection=[
            ("0", "Ninguna"),
            ("1", "Física"),
            ("2", "Visual"),
            ("3", "Auditiva"),
            ("4", "Intelectual"),
            ("5", "Otra"),
        ],
        string="Tipo de discapacidad (código MinTrab)",
        default="0",
    )

    _sql_constraints = [
        ("l10n_gt_dpi_uniq", "unique(l10n_gt_dpi, company_id)",
         "El DPI ya está registrado para otro empleado."),
    ]

    @api.constrains("l10n_gt_dpi")
    def _check_dpi(self):
        for emp in self.filtered("l10n_gt_dpi"):
            digits = emp.l10n_gt_dpi.replace(" ", "")
            if not digits.isdigit() or len(digits) != 13:
                raise ValidationError(
                    "El DPI debe contener exactamente 13 dígitos (empleado %s)." % emp.name
                )
