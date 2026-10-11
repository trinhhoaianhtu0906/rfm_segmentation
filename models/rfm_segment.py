from odoo import fields, models


class RfmSegment(models.Model):
    _name = "rfm.segment"
    _description = "RFM Segment"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    partner_ids = fields.One2many("res.partner", "rfm_segment_id", string="Customers")

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "The segment code must be unique.",
    )
