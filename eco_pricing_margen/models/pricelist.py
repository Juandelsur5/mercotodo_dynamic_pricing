# -*- coding: utf-8 -*-

from odoo import models
from odoo.exceptions import UserError


class Pricelist(models.Model):
    _inherit = 'product.pricelist'

    def _get_tax_rate_for_product(self, product, partner=None):
        """Obtiene la tasa de IVA aplicable al producto considerando la posición fiscal del partner.
        
        Args:
            product: product.product record
            partner: res.partner record (opcional)
        
        Returns:
            float: Tasa de IVA en decimal (ej: 0.19 para 19%, 0.0 si no aplica)
        """
        # Obtener impuestos del producto
        taxes = product.taxes_id
        if not taxes:
            return 0.0
        
        # Si hay partner, considerar su posición fiscal
        if partner:
            # Obtener posición fiscal del partner
            fiscal_position = partner.property_account_position_id
            if fiscal_position:
                # Mapear impuestos según posición fiscal
                taxes = fiscal_position.map_tax(taxes)
        
        # Buscar la mayor tasa de IVA entre los impuestos aplicables
        max_tax_rate = 0.0
        for tax in taxes:
            if tax.type_tax_use == 'sale' and tax.amount_type == 'percent':
                max_tax_rate = max(max_tax_rate, tax.amount / 100.0)
        
        return max_tax_rate

    def _compute_price_rule(self, products_qty_partner, date=False, uom_id=False):
        # Ejecutar primero el motor nativo
        result = super()._compute_price_rule(products_qty_partner, date, uom_id)

        # Determinar canal según nombre de la lista
        pricelist_name = (self.name or '').upper()
        margin_field = None

        if 'T.A.T' in pricelist_name or 'PRECIO T.A.T' in pricelist_name:
            margin_field = 'x_margin_tat'
        elif 'MAYORISTA' in pricelist_name or 'MAYORISTAS' in pricelist_name:
            margin_field = 'x_margin_mayorista'
        elif 'P.O.S' in pricelist_name or 'POS' in pricelist_name:
            margin_field = 'x_margin_pos'
        elif 'OFERTA' in pricelist_name or 'OFERTAS' in pricelist_name:
            margin_field = 'x_margin_oferta'

        # Si la lista no corresponde a un canal controlado, no intervenir
        if not margin_field:
            return result

        # Recalcular precio por producto según utilidad del producto
        for product_id, qty, partner in products_qty_partner:
            if product_id not in result:
                continue

            product = self.env['product.product'].browse(product_id)
            if not product.exists():
                continue

            tmpl = product.product_tmpl_id
            margin_value = getattr(tmpl, margin_field, False)

            # Bloqueo real: sin utilidad definida no se vende por este canal
            if not margin_value or margin_value <= 0:
                raise UserError(
                    f'El producto "{tmpl.display_name}" no tiene utilidad definida '
                    f'para el canal de esta lista de precios.'
                )

            costo = tmpl.standard_price
            if not costo or costo <= 0:
                continue

            # Calcular precio sin IVA basado en margen
            # El margen se calcula sobre el precio neto antes de impuestos
            utilidad = margin_value / 100.0
            precio_sin_iva = costo / (1 - utilidad)
            
            # El precio retornado debe ser sin IVA, ya que Odoo aplicará los impuestos
            # según la posición fiscal del partner en el momento de la venta
            # Esto permite manejar correctamente responsables y no responsables de IVA

            # Respetar contrato del motor de precios
            result[product_id] = (False, precio_sin_iva)

        return result
