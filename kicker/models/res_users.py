from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _signup_create_user(self, values):
        """ 
        Create users as inactive by default.
        
        Override the public signup user to be inactive by default, requiring an
        admin to re-activate it once the signup request is established as valid.
        """
        new_user = super()._signup_create_user(values)
        new_user.active = False
        return new_user

