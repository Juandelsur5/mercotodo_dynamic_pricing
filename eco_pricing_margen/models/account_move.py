from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        res = super().action_post()

        for move in self:
            if move.move_type in ["in_invoice", "in_refund"]:
                for line in move.invoice_line_ids:
                    if line.product_id and line.quantity:
                        cost_unit = line.price_subtotal / line.quantity
                        line.product_id.product_tmpl_id.x_cost_base = cost_unit

        return res
