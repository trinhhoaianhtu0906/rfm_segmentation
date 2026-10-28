from bisect import bisect_left
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

SOURCE_MODELS = {
    "account_move": "account.move",
    "sale_order": "sale.order",
    "pos_order": "pos.order",
}


def quintile_scores(values):
    """Score each value from 1 to 5 by its percent rank: the bottom fifth
    gets 1, the top fifth 5. Equal values get the same score."""
    ordered = sorted(values)
    count = len(ordered)
    return [
        min(5, 1 + 5 * bisect_left(ordered, value) // count) for value in values
    ]


class RfmCalculator(models.AbstractModel):
    _name = "rfm.calculator"
    _description = "RFM Calculator"

    @api.model
    def _period_start(self, company):
        today = fields.Date.context_today(self)
        return today - relativedelta(months=company.rfm_period_months)

    @api.model
    def _fetch_account_move(self, company):
        """Return {commercial partner id: (last date, count, amount)} from the
        posted customer invoices of the period. Credit notes lower the amount
        but don't count as purchases."""
        groups = self.env["account.move"]._read_group(
            [
                ("company_id", "=", company.id),
                ("state", "=", "posted"),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("invoice_date", ">=", self._period_start(company)),
            ],
            ["commercial_partner_id", "move_type"],
            ["invoice_date:max", "__count", "amount_untaxed_signed:sum"],
        )
        data = {}
        refunds = {}
        for partner, move_type, last_date, count, amount in groups:
            if move_type == "out_invoice":
                data[partner.id] = [last_date, count, amount]
            else:
                refunds[partner.id] = amount
        for partner_id, amount in refunds.items():
            if partner_id in data:
                data[partner_id][2] += amount
        return {key: tuple(value) for key, value in data.items()}

    @api.model
    def _fetch_orders(self, model, domain, amount_fields, company):
        """Sum orders of ``model`` per commercial partner, converting the
        amounts to the company currency with the rate stored on the order."""
        start = datetime.combine(self._period_start(company), time.min)
        groups = self.env[model]._read_group(
            [
                *domain,
                ("company_id", "=", company.id),
                ("partner_id", "!=", False),
                ("date_order", ">=", start),
            ],
            ["partner_id", "currency_rate"],
            ["date_order:max", "__count", *(f"{f}:sum" for f in amount_fields)],
        )
        data = {}
        for partner, rate, last_order, count, *amounts in groups:
            amount = (amounts[0] - sum(amounts[1:])) / (rate or 1.0)
            last_date = last_order.date()
            key = partner.commercial_partner_id.id
            if key in data:
                prev_date, prev_count, prev_amount = data[key]
                last_date = max(last_date, prev_date)
                count += prev_count
                amount += prev_amount
            data[key] = (last_date, count, amount)
        return data

    @api.model
    def _fetch_sale_order(self, company):
        return self._fetch_orders(
            "sale.order", [("state", "=", "sale")], ["amount_untaxed"], company
        )

    @api.model
    def _fetch_pos_order(self, company):
        return self._fetch_orders(
            "pos.order",
            [("state", "in", ("paid", "done"))],
            ["amount_total", "amount_tax"],
            company,
        )

    @api.model
    def _compute_rfm(self, company):
        """Score the customers of ``company`` from its configured source, put
        them in a segment and clear the customers without purchases in the
        period."""
        self = self.sudo()
        source = company.rfm_source
        if SOURCE_MODELS.get(source) not in self.env:
            raise UserError(
                self.env._("The RFM source %s is not installed.", source or "-")
            )
        data = getattr(self, f"_fetch_{source}")(company)

        today = fields.Date.context_today(self)
        partner_ids = list(data)
        rows = [data[partner_id] for partner_id in partner_ids]
        recency_days = [(today - last_date).days for last_date, _c, _a in rows]
        r_scores = quintile_scores([-days for days in recency_days])
        f_scores = quintile_scores([count for _d, count, _a in rows])
        m_scores = quintile_scores([amount for _d, _c, amount in rows])

        segments = self.env["rfm.segment"].search([])
        partners = self.env["res.partner"].with_context(tracking_disable=True)
        for partner_id, (_d, count, amount), days, r, f, m in zip(
            partner_ids, rows, recency_days, r_scores, f_scores, m_scores
        ):
            partners.browse(partner_id).write(
                {
                    "rfm_recency_days": days,
                    "rfm_frequency": count,
                    "rfm_monetary": amount,
                    "rfm_recency_score": r,
                    "rfm_frequency_score": f,
                    "rfm_monetary_score": m,
                    "rfm_segment_id": segments._match(r, f).id,
                }
            )

        stale = partners.with_context(active_test=False).search(
            [
                ("id", "not in", partner_ids),
                "|",
                ("rfm_recency_score", "!=", 0),
                ("rfm_segment_id", "!=", False),
            ]
        )
        stale.write(
            {
                "rfm_recency_days": 0,
                "rfm_frequency": 0,
                "rfm_monetary": 0.0,
                "rfm_recency_score": 0,
                "rfm_frequency_score": 0,
                "rfm_monetary_score": 0,
                "rfm_segment_id": False,
            }
        )
        company.sudo().rfm_last_compute = fields.Datetime.now()

    @api.model
    def _cron_compute_rfm(self):
        self._compute_rfm(self.env.company)
