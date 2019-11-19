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

    NUM_BG = 10

    @http.route(['/free', '/free/<model("kicker.kicker"):kicker>'], type='http', auth="public")
    def is_the_kicker_free(self, kicker=None, **kw):
        if not kicker:
            kicker = request.env['kicker.kicker'].sudo().search([], limit=1)
        if not kicker:
            return request.not_found()
        rand_bg = random.randrange(0, self.NUM_BG - 1, step=1)
        return request.render('kicker.page_is_free', {
            'is_free': kicker.is_available,
            'bg': ('yes_%s' if kicker.is_available else 'no_%s') % rand_bg,
        })

    @http.route(['/kicker/ping'], auth='none', csrf=False)
    def ping(self, token=False, status="", **kw):
        """
            TEST URL:
                /kicker/ping?token=123-456789-321&status={"available": True,"temperature":"15.4"}
        """
        with api.Environment.manage():
            if token:
                try:
                    ip_address = request.httprequest.environ['REMOTE_ADDR']
                    payload = ast.literal_eval(status)
                    available = status.get('available', False)
                    return request.env['kicker.ping'].sudo().ping(token, available, ip_address)
                except Exception as err:
                    _logger.error("Kicker Ping failed when evaluting status")
            return False

    @http.route(['/app/', "/app/<path:route>"], auth="user")
    @check_kicker_user
    def app(self, **kw):
        return request.render('kicker.app', {'body_classname': 'o_kicker_app', 'user': request.env.user})

    @http.route(['/app/static/<path:route>'], auth="none")
    def static(self, route, **kw):
        """Serve static files via the /app route for caching purposes (servicewsorker scope)"""
        return werkzeug.utils.redirect('/kicker/static/' + route)

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
    def update_profile(self, name, tagline, main_kicker, avatar=None, **kw):
        partner = request.env.user.partner_id
        vals = {
            'name': name,
            'tagline': tagline,
            'main_kicker_id': False if int(main_kicker) == -1 else int(main_kicker),
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
        if not (team1 or team2):
            raise UserError(_('There must be at least one registered player in the teams composition!'))
        game = request.env['kicker.game'].sudo().create({
            'kicker_id': kicker_id,
            'score_1': post.get('score1'),
            'score_2': post.get('score2'),
            'session_ids':[(0, False, {'player_id': team1 and team1[0], 'team': 'team_1'}),
                           (0, False, {'player_id': len(team1) > 1 and team1[1], 'team': 'team_1'}),
                           (0, False, {'player_id': team2 and team2[0], 'team': 'team_2'}),
                           (0, False, {'player_id': len(team2) > 1 and team2[1], 'team': 'team_2'}),],
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

    @http.route('/app/sw.js', type='http', auth='public')
    def serviceworker(self, **kw):
        bundles = ['web.assets_common', 'web.assets_frontend']
        attachments = request.env['ir.attachment']
        for bundle in bundles:
            attachments += attachments.search([
                ('url', '=like', '/web/content/%-%/{0}%'.format(bundle))
            ])
        urls = attachments.mapped('url')
        js = request.env['ir.ui.view'].render_template('kicker.service_worker', values={'urls': urls, 'version': SERVER_START})
        headers = {
            'Content-Type': 'text/javascript',
        }
        response = http.request.make_response(js, headers=headers)
        return response

    # ------------------------------------------------------
    # Login - overwrite of the web login so that regular users are redirected to the backend
    # while portal users are redirected to the kicker app
    # ------------------------------------------------------

    @http.route(auth="public")
    def web_login(self, redirect=None, *args, **kw):
        response = super(KickerController, self).web_login(redirect=redirect, *args, **kw)
        if not redirect and request.params['login_success']:
            if request.env.user.has_group('base.group_user'):
                redirect = b'/web?' + request.httprequest.query_string
            elif request.env.user.kicker_player:
                redirect = '/app'
            else:
                redirect = '/'
            return http.redirect_with_hash(redirect)
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