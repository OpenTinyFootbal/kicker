
{
    'name': 'Kicker App',
    'version': '1.0',
    'category': 'Kicker',
    'sequence': 6,
    'summary': 'Kicker in the Lunch Room',
    'website': 'https://kicker.odoo.com',
    'depends': ['http_routing', 'bus', 'web_editor', 'auth_signup'],
    'data': [
        'security/kicker_security.xml',
        'security/ir.model.access.csv',
        'views/kicker_templates.xml',
        'views/kicker_views.xml',
        'data/kicker_data.xml',
        'data/mail_templates.xml',
    ],
    'demo': [
        'data/kicker_demo.xml',
    ],
    'application': True,
}
