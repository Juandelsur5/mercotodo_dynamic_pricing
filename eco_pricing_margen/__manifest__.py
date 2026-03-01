# -*- coding: utf-8 -*-
{
    'name': 'Eco Pricing Margen',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Gestión de márgenes de contribución y automatización de precios desde compras',
    'author': 'Juandelsur5',
    'depends': ['product', 'account', 'purchase', 'sale'],  # Dependencias universales
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

