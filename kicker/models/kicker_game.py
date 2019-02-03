import odoo
from odoo import api, fields, models


class KickerGame(models.Model):
    _name = 'kicker.game'
    _description = 'Kicker Game'
    _rec_name = 'create_date'
    _order = 'create_date DESC'

    create_date = fields.Datetime(default=fields.Datetime.now)
    kicker_id = fields.Many2one('kicker.kicker', string='Kicker', ondelete='restrict', index=True)
    winning_team = fields.Selection([('team_1', 'Team 1'), ('team_2', 'Team 2')], compute='_compute_winning_team', store=True)
    score_1 = fields.Integer(string="Team 1 Score", required=True)
    score_2 = fields.Integer(string="Team 2 Score", required=True)
    session_ids = fields.One2many('kicker.session', 'game_id', string='Sessions')
    
    @api.depends('score_1', 'score_2')
    def _compute_winning_team(self):
        for game in self:
            game.winning_team = 'team_1' if game.score_1 > game.score_2 else 'team_2'

class KickerSession(models.Model):
    _name = 'kicker.session'
    _description = 'Kicker Session'

    game_id = fields.Many2one('kicker.game', required=True, index=True)
    won = fields.Boolean(compute='_compute_won', store=True)
    team = fields.Selection([('team_1', 'Team 1'), ('team_2', 'Team 2')], required=True)
    player_id = fields.Many2one('res.partner', string='Player', index=True)
    game_date = fields.Datetime(related='game_id.create_date', store=True)

    @api.depends('game_id', 'game_id.winning_team')
    def _compute_won(self):
        for session in self:
            session.won = session.team == session.game_id.winning_team
