from odoo import api, models, fields
from odoo import tools


class KickerStat(models.Model):
    _auto = False
    _name = "kicker.stat"
    _description = "Kicker Statistic"
    _rec_name = 'date'
    _order = 'date desc'

    player_id = fields.Many2one('res.partner', string='Player', readonly=True)
    session_id = fields.Many2one('kicker.session', string='Session', readonly=True)
    game_id = fields.Many2one('kicker.game', string='Game', readonly=True)
    date = fields.Datetime('Game Date', readonly=True)
    won = fields.Boolean('Won', readonly=True)
    teammate_id = fields.Many2one('res.partner', string='Teammate', readonly=True)
    opponent1_id = fields.Many2one('res.partner', string='Opponent 1', readonly=True)
    opponent2_id = fields.Many2one('res.partner', string='Opponent 2', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            s.id as id,
            s.id as session_id,
            g.id as game_id,
            p.id as player_id,
            s.won as won,
            g.date as date,
            tm.id as teammate_id,
            o1.id as opponent1_id,
            o2.id as opponent2_id
        """

        for field in fields.values():
            select_ += field

        from_ = """
                kicker_session s
                    join kicker_game g on (g.id = s.game_id)
                    join res_partner p on s.player_id = p.id
                    join kicker_session sm on (sm.game_id=g.id and sm.team=s.team and sm.player_id!=s.player_id)
                    join res_partner tm on (sm.player_id=tm.id)
                    join kicker_session os1 on os1.game_id=g.id and os1.team!=s.team
                    join res_partner o1 on o1.id=os1.player_id
                    join kicker_session os2 on os2.game_id=g.id and os2.team!=s.team and os2.id>os1.id
                    join res_partner o2 on o2.id=os2.player_id
                %s
        """ % from_clause

        groupby_ = """
            s.id,
            p.id,
            tm.id,
            o1.id,
            o2.id,
            g.id,
            s.won %s
        """ % (groupby)

        return '%s (SELECT %s FROM %s GROUP BY %s)' % (with_, select_, from_, groupby_)

    @api.model_cr
    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))