import ast
import base64
import functools
import jinja2
import logging
import random
import re
import datetime
from functools import reduce
import werkzeug

from odoo import SUPERUSER_ID
from odoo import api, http, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.modules import get_module_resource
from odoo.addons.kicker.tools.image import image_process
from odoo.addons.web.controllers.main import Home
from odoo.addons.auth_signup.controllers.main import AuthSignupHome

_logger = logging.getLogger(__name__)

SERVER_START = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d-%H%M')

def check_kicker_user(func):
    """Check that a user is correctly set up for accessing kicker-related resources."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        user = request.env.user
        if not user.kicker_player:
            _logger.warn('user %s tried to access kicker-protected data but is not a kicker player', user.login)
            raise werkzeug.exceptions.Forbidden()
        return func(*args, **kwargs)
    return wrapper

class KickerController(Home):

    # JSON routes
    @http.route('/app/json/dashboard', type='json', auth='user', csrf=False)
    @check_kicker_user
    def dashboard(self, **kw):
        partner = request.env.user.partner_id
        return partner._dashboard_stats()

    @http.route('/app/json/rankings', type='json', auth='user', csrf=False)
    @check_kicker_user
    def rankings(self, period='month', **kw):
        partner = request.env.user.partner_id.sudo()
        return partner._get_rankings(period=period)


    @http.route('/app/json/community', type='json', auth='user', csrf=False)
    @check_kicker_user
    def community(self, **kw):
        partner = request.env.user.partner_id
        return partner._community_stats()

    @http.route(['/app/json/player', '/app/json/player/<int:player_id>'], type='json', auth='user')
    @check_kicker_user
    def player_info(self, player_id=None, **kw):
        if not player_id:
            player_id = request.env.user.partner_id.id
        partner = request.env['res.partner'].browse(player_id)
        if not partner:
            raise werkzeug.exceptions.NotFound()
        fields = ['id', 'name', 'email', 'main_kicker_id', 'tagline',
                  'wins', 'losses', 'win_ratio', 'weekly_wins', 'weekly_losses', 'weekly_win_ratio']
        return partner.sudo().read(fields)[0]

    @http.route('/app/json/update_profile', type='json', auth='user', methods=['POST'], csrf=False)
    @check_kicker_user
    def update_profile(self, name, tagline=None, main_kicker=None, avatar=None, **kw):
        partner = request.env.user.partner_id
        vals = {
            'name': name,
            'tagline': tagline,
            'main_kicker_id': int(main_kicker) if main_kicker else False,
        }
        if avatar:
            avatar = image_process(avatar, size=(512,512), crop=True)
            vals['image_1920'] = avatar
        partner.write(vals)
        return {'success': True, 'player':partner.read(['id', 'name', 'email', 'main_kicker_id', 'tagline'])[0]}

    @http.route(['/app/json/players'], type='json', auth='user')
    @check_kicker_user
    def list_players(self, **kw):
        return {
            "players": request.env['res.partner'].search_read([('kicker_player', '=', True)], fields=['id', 'name']),
            "player_id":  request.env.user.partner_id.id
        }

    @http.route(['/app/json/kickers'], type='json', auth='user')
    @check_kicker_user
    def list_kickers(self, **kw):
        kickers = request.env['kicker.kicker'].sudo().search_read([], fields=['id', 'name'])
        default = request.env.user.partner_id.main_kicker_id.id
        return {'kickers': kickers, 'default': default}

    @http.route(['/kicker/score/submit'], type='json', auth='user', methods=['POST'], csrf=False)
    @check_kicker_user
    def submit_score(self, **post):
        team1 = post.get('team1')
        team2 = post.get('team2')
        kicker_id = post.get('kicker_id')
        _logger.info(post)
        public_player = request.env.ref('kicker.anon_res_partner')
        player11 = team1[0] or public_player.id
        player12 = team1[1] or public_player.id
        player21 = team2[0] or public_player.id
        player22 = team2[1] or public_player.id
        if not (team1 or team2) or not (team1[0] or team1[1] or team2[0] or team2[1]):
            raise UserError(_('There must be at least one registered player in the teams composition!'))
        if not post.get('score1') and post.get('score2'):
            raise UserError(_('Please input the score'))
        game = request.env['kicker.game'].sudo().create({
            'kicker_id': kicker_id,
            'score_1': post.get('score1'),
            'score_2': post.get('score2'),
            'session_ids':[(0, False, {'player_id': player11, 'team': 'team_1'}),
                           (0, False, {'player_id': player12, 'team': 'team_1'}),
                           (0, False, {'player_id': player21, 'team': 'team_2'}),
                           (0, False, {'player_id': player22, 'team': 'team_2'}),],
        })
        return {'success': True, 'game_id': game.id}

    # Non-json routes
    @http.route(['/app/avatar', '/app/avatar/<int:player_id>'], type='http', auth="public")
    def avatar(self, player_id=None, **kw):
        if not player_id:
            player_id = request.env.user.partner_id.id
        status, headers, content = request.env['ir.http'].sudo().binary_content(model='res.partner', id=player_id, field='image_256', default_mimetype='image/png')

        if not content:
            img_path = get_module_resource('web', 'static/src/img', 'placeholder.png')
            with open(img_path, 'rb') as f:
                image = f.read()
            content = base64.b64encode(image)
        if status == 304:
            return werkzeug.wrappers.Response(status=304)
        image_base64 = base64.b64decode(content)
        headers.append(('Content-Length', len(image_base64)))
        response = request.make_response(image_base64, headers)
        response.status = str(status)
        return response

class KickerSignupController(AuthSignupHome):

    def do_signup(self, qcontext):
        email = qcontext.get('login')
        name = qcontext.get('name')
        if request.env['res.users'].sudo().with_context(active_test=False).search([('login', '=', name)]):
            raise UserError(_("This user name is already in use."))
        if not re.match(r"^\w+$", name):
            raise UserError(_("You login can only contain letters (case-sensitive), numbers or underscores (_). You will be able to change your app handle in the app later on."))
        if email:
            if not re.match(r"^\w{3}@odoo.com$", email):
                raise UserError(_("Please use an email in the format <trigram>@odoo.com"))
        return super().do_signup(qcontext)

    @http.route('/kicker/signup', auth='public', type='json', methods=['POST'])
    def kicker_signup(self, login, password, email):
        if request.env['res.users'].sudo().with_context(active_test=False).search([('login', '=', login)]):
            raise UserError(_("This user name is already in use."))
        if not re.match(r"^\w+$", login):
            raise UserError(_("Your login can only contain letters (case-sensitive), numbers or underscores (_). You will be able to change your handle in the app later on."))
        if email:
            if not re.match(r"^\w{3}@odoo.com$", email):
                raise UserError(_("Please use an email in the format <trigram>@odoo.com"))
        portal_group = request.env.ref('base.group_portal')
        request.env['res.users'].sudo().with_context(no_reset_password=True).create({'name': login, 'email': email, 'login': login, 'password': password, 'groups_id': [(4, portal_group.id, False)]})