# -*- coding: utf-8 -*-
{
    'name': "hc_mat_transfer",

    'summary': """
        import transfer""",

    'description': """
        import transfer
    """,

    'author': "Chlpn",
    'website': "http://www.hashcodeit.com",

    'category': 'stock',
    'version': '14.0.1.0.1',

    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/picking_view.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
    'auto_install': False,
}
