# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import AccessError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Campos de Margen (Editables solo por el Contador)
    x_margin_tat = fields.Float(string='% Margen T.A.T', default=0.0, groups='eco_pricing_margen.group_margen_precios')
    x_margin_mayorista = fields.Float(string='% Margen Mayorista', default=0.0, groups='eco_pricing_margen.group_margen_precios')
    x_margin_pos = fields.Float(string='% Margen P.O.S', default=0.0, groups='eco_pricing_margen.group_margen_precios')
    x_margin_oferta = fields.Float(string='% Margen Oferta', default=0.0, groups='eco_pricing_margen.group_margen_precios')

    def write(self, vals):
        """
        Sobrescribir write para proteger campos de margen y costo.
        
        SINCRONIZACIÓN CRÍTICA DE COSTOS - Doble Origen:
        
        Origen A (Automático - Factura):
        - Las facturas de proveedor usan sudo() en account_move.py
        - Bypass de esta validación: actualización directa desde documento legal
        - Dispara recálculo inmediato via @api.depends('standard_price', ...)
        
        Origen B (Manual - Contador):
        - Usuario con grupo margen_precios puede editar directamente
        - Validación de seguridad: bloquea edición sin permiso
        - Dispara recálculo inmediato via @api.depends('standard_price', ...)
        
        EFECTO DOMINÓ EN CASCADA:
        - Cualquier cambio en standard_price recalcula automáticamente:
          * x_price_tat_con_iva
          * x_price_mayorista_con_iva
          * x_price_pos_con_iva
          * x_price_oferta_con_iva
        """
        # Campos protegidos que solo pueden editar usuarios con grupo margen_precios
        protected_fields = ['x_margin_tat', 'x_margin_mayorista', 'x_margin_pos', 'x_margin_oferta', 'standard_price']
        
        # Verificar si se intenta modificar algún campo protegido
        if any(field in vals for field in protected_fields):
            # Verificar permisos: solo grupo margen_precios puede editar manualmente
            # Nota: Las facturas usan sudo() y no pasan por esta validación
            if not self.env.user.has_group('eco_pricing_margen.group_margen_precios'):
                raise AccessError(
                    'Solo usuarios con el grupo "margen_precios" pueden modificar '
                    'los márgenes de utilidad y el costo del producto manualmente. '
                    'El costo se actualiza automáticamente desde las facturas de compra.'
                )
        
        # Ejecutar write: esto dispara @api.depends y recálculo en cascada
        return super(ProductTemplate, self).write(vals)

    # Precios Calculados Sin IVA
    x_price_tat_sin_iva = fields.Float(string='Precio T.A.T sin IVA', compute='_compute_prices_all_channels', store=True)
    x_price_mayorista_sin_iva = fields.Float(string='Precio Mayorista sin IVA', compute='_compute_prices_all_channels', store=True)
    x_price_pos_sin_iva = fields.Float(string='Precio P.O.S sin IVA', compute='_compute_prices_all_channels', store=True)
    x_price_oferta_sin_iva = fields.Float(string='Precio Oferta sin IVA', compute='_compute_prices_all_channels', store=True)

    # Precios Totales Con IVA (REGLA DE ORO: store=True para evitar OwlError)
    # store=True asegura que los campos se almacenen en BD y sean accesibles desde el frontend
    x_price_tat_con_iva = fields.Float(string='Total T.A.T con IVA', compute='_compute_prices_all_channels', store=True)
    x_price_mayorista_con_iva = fields.Float(string='Total Mayorista con IVA', compute='_compute_prices_all_channels', store=True)
    x_price_pos_con_iva = fields.Float(string='Total P.O.S con IVA', compute='_compute_prices_all_channels', store=True)
    x_price_oferta_con_iva = fields.Float(string='Total Oferta con IVA', compute='_compute_prices_all_channels', store=True)

    @api.depends('standard_price', 'x_margin_tat', 'x_margin_mayorista', 'x_margin_pos', 'x_margin_oferta', 'taxes_id')
    def _compute_prices_all_channels(self):
        """
        RECÁLCULO INMEDIATO EN CASCADA - Motor Dinámico del Sistema
        
        Este método es el corazón del sistema de precios. Se ejecuta automáticamente
        cuando cambia cualquiera de los campos dependientes, disparando un efecto
        dominó que actualiza todos los precios de los 4 canales.
        
        Disparadores de Recálculo:
        - Cambio en standard_price (desde factura o manual)
        - Cambio en porcentaje de utilidad (x_margin_*)
        - Cambio en impuestos del producto (taxes_id)
        
        Fórmula de Margen de Contribución:
        Precio sin IVA = Costo / (1 - %Margen)
        Precio con IVA = (Costo / (1 - %Margen)) × (1 + %IVA)
        
        Ventajas:
        - Actualización en tiempo real sin guardar (calculadora dinámica)
        - Protege la utilidad neta antes de impuestos
        - Sincronización automática con costo real
        
        IMPORTANTE - REGLA DE ORO (store=True):
        Todos los campos computados usan store=True para evitar errores de referencia
        en el frontend (OwlError). El decorador @api.depends asegura que los cambios
        se reflejen cuando se guarda el formulario, manteniendo la sincronización
        automática con el costo y los márgenes.
        """
        for record in self:
            costo = record.standard_price or 0.0
            
            # Obtenemos la tasa de IVA actual del producto (ej: 19.0, 5.0, 0.0)
            # Sumamos solo los impuestos de venta de tipo porcentual
            sale_taxes = record.taxes_id.filtered(lambda t: t.type_tax_use == 'sale' and t.amount_type == 'percent')
            tax_rate = sum(sale_taxes.mapped('amount')) / 100.0 if sale_taxes else 0.0
            
            # Función interna para el margen de contribución: Costo / (1 - Margen)
            # Esta fórmula protege la utilidad neta antes de impuestos
            def calc_neto(margen):
                if not margen or margen <= 0 or margen >= 100:
                    return 0.0
                if not costo or costo <= 0:
                    return 0.0
                # Fórmula de Margen de Contribución
                return costo / (1 - (margen / 100.0))

            # Cálculo de Precios Sin IVA (Base técnica)
            precio_tat_sin = calc_neto(record.x_margin_tat)
            precio_may_sin = calc_neto(record.x_margin_mayorista)
            precio_pos_sin = calc_neto(record.x_margin_pos)
            precio_oferta_sin = calc_neto(record.x_margin_oferta)
            
            record.x_price_tat_sin_iva = precio_tat_sin
            record.x_price_mayorista_sin_iva = precio_may_sin
            record.x_price_pos_sin_iva = precio_pos_sin
            record.x_price_oferta_sin_iva = precio_oferta_sin

            # Cálculo de Precios Con IVA (Total Venta - Actualización automática)
            # Transparencia contable: Total = Costo + Utilidad + IVA
            record.x_price_tat_con_iva = precio_tat_sin * (1 + tax_rate)
            record.x_price_mayorista_con_iva = precio_may_sin * (1 + tax_rate)
            record.x_price_pos_con_iva = precio_pos_sin * (1 + tax_rate)
            record.x_price_oferta_con_iva = precio_oferta_sin * (1 + tax_rate)
