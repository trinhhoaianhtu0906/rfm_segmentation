from odoo import api, fields, models

from .rfm_calculator import SOURCE_MODELS


class ResCompany(models.Model):
    _inherit = "res.company"

    rfm_source = fields.Selection(
        selection="_selection_rfm_source",
        string="RFM source",
        default="account_move",
    )
    rfm_period_months = fields.Integer(string="RFM period (months)", default=12)
    rfm_last_compute = fields.Datetime(string="RFM last computed", readonly=True)

    _rfm_period_positive = models.Constraint(
        "CHECK(rfm_period_months > 0)",
        "The RFM period must be at least one month.",
    )

    @api.model
    def _selection_rfm_source(self):
        labels = {
            "account_move": self.env._("Customer invoices"),
            "sale_order": self.env._("Sales orders"),
            "pos_order": self.env._("Point of Sale orders"),
        }
        return [
            (source, labels[source])
            for source, model in SOURCE_MODELS.items()
            if model in self.env
        ]
