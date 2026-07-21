# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nGtEconomicZone(models.Model):
    """Circunscripción económica para el salario mínimo (§4.1.4 del diseño)."""

    _name = "l10n.gt.economic.zone"
    _description = "Circunscripción económica (Guatemala)"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    minimum_wage_ids = fields.One2many(
        "l10n.gt.minimum.wage", "zone_id", string="Salarios mínimos"
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código de circunscripción debe ser único."),
    ]

    def get_minimum_wage(self, date):
        """Salario mínimo mensual vigente para la zona en una fecha dada."""
        self.ensure_one()
        wage = self.env["l10n.gt.minimum.wage"].search(
            [("zone_id", "=", self.id), ("date_from", "<=", date)],
            order="date_from desc",
            limit=1,
        )
        return wage.amount if wage else 0.0


class L10nGtMinimumWage(models.Model):
    """Salario mínimo vigente por circunscripción y fecha (§7.3)."""

    _name = "l10n.gt.minimum.wage"
    _description = "Salario mínimo por circunscripción"
    _order = "zone_id, date_from desc"

    zone_id = fields.Many2one(
        "l10n.gt.economic.zone", string="Circunscripción", required=True,
        ondelete="cascade",
    )
    date_from = fields.Date("Vigente desde", required=True)
    amount = fields.Monetary("Salario mínimo mensual", required=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda s: s.env.ref("base.GTQ", raise_if_not_found=False)
    )

    @api.constrains("amount")
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError("El salario mínimo debe ser mayor que cero.")
