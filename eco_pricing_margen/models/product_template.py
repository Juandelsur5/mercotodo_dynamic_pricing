from odoo import models, fields, api
from odoo.tools.float_utils import float_round


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_cost_base = fields.Float(
        string="Costo Base",
        company_dependent=True,
        digits="Product Price",
    )

    x_utility_pct_tat = fields.Float(company_dependent=True)
    x_utility_pct_pos = fields.Float(company_dependent=True)
    x_utility_pct_mayorista = fields.Float(company_dependent=True)
    x_utility_pct_oferta = fields.Float(company_dependent=True)

    x_final_price_tat = fields.Float(compute="_compute_prices", store=True)
    x_final_price_pos = fields.Float(compute="_compute_prices", store=True)
    x_final_price_mayorista = fields.Float(compute="_compute_prices", store=True)
    x_final_price_oferta = fields.Float(compute="_compute_prices", store=True)

    @api.depends(
        "x_cost_base",
        "x_utility_pct_tat",
        "x_utility_pct_pos",
        "x_utility_pct_mayorista",
        "x_utility_pct_oferta",
        "taxes_id",
    )
    def _compute_prices(self):
        for product in self:
            tax_rate = 0.0
            sale_taxes = product.taxes_id.filtered(
                lambda t: t.type_tax_use == "sale" and t.amount_type == "percent"
            )
            if sale_taxes:
                tax_rate = sum(sale_taxes.mapped("amount")) / 100.0

            def compute_price(cost, utility):
                if not cost:
                    return 0.0
                price_excl = cost * (1 + (utility or 0.0) / 100.0)
                price_incl = price_excl * (1 + tax_rate)
                return float_round(
                    price_incl,
                    precision_rounding=product.currency_id.rounding,
                )

            product.x_final_price_tat = compute_price(
                product.x_cost_base, product.x_utility_pct_tat
            )
            product.x_final_price_pos = compute_price(
                product.x_cost_base, product.x_utility_pct_pos
            )
            product.x_final_price_mayorista = compute_price(
                product.x_cost_base, product.x_utility_pct_mayorista
            )
            product.x_final_price_oferta = compute_price(
                product.x_cost_base, product.x_utility_pct_oferta
            )
