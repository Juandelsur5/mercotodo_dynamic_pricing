# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=False):
        """
        Sobrescribir el método _post para actualizar el costo de los productos
        cuando se valida una factura de proveedor (in_invoice).
        """
        res = super(AccountMove, self)._post(soft=soft)
        
        # Procesar todas las facturas de proveedor en el conjunto
        for move in self:
            if move.move_type == 'in_invoice':
                move._update_product_costs_from_invoice()
        
        return res

    def _update_product_costs_from_invoice(self):
        """
        ORIGEN A: Actualización Automática desde Factura de Proveedor
        
        Hook crítico que sincroniza el costo del producto con el precio unitario
        neto de la factura de compra. Este es el punto de entrada automático
        que permite al Auxiliar actualizar costos solo a través de documentos legales.
        
        Flujo:
        1. Auxiliar valida factura de proveedor (in_invoice)
        2. Sistema extrae price_unit neto de cada línea
        3. Actualiza standard_price del producto (usando sudo() para bypass de seguridad)
        4. Dispara recálculo inmediato via @api.depends en product.template
        5. Todos los precios con IVA se actualizan automáticamente
        
        Seguridad:
        - Usa sudo() para bypass de restricciones de grupo
        - Solo procesa facturas de proveedor (in_invoice)
        - price_unit ya es precio neto (sin impuestos)
        """
        for line in self.invoice_line_ids:
            if line.product_id and line.price_unit:
                product_tmpl = line.product_id.product_tmpl_id
                if product_tmpl:
                    # Actualización automática del costo desde factura
                    # sudo() permite bypass de restricciones: actualización desde documento legal
                    # Esto dispara inmediatamente @api.depends('standard_price', ...) 
                    # y recálculo en cascada de todos los precios
                    product_tmpl.sudo().standard_price = line.price_unit


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def write(self, vals):
        """
        Actualizar costo del producto cuando se modifica una línea de factura de proveedor
        que ya está validada (posted).
        """
        res = super(AccountMoveLine, self).write(vals)
        
        # Si se modifica el price_unit en una factura de proveedor ya validada
        if 'price_unit' in vals:
            for line in self:
                if (line.move_id.move_type == 'in_invoice' and 
                    line.move_id.state == 'posted' and 
                    line.product_id and 
                    line.price_unit):
                    # Actualizar costo del producto
                    line.product_id.product_tmpl_id.sudo().standard_price = line.price_unit
        
        return res

