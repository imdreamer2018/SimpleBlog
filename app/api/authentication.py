from flask import g,jsonify
from flask_httpauth import HTTPBasicAuth
from ..models import User
from . import api
from .errors import unauthorized,forbidden

auth = HTTPBasicAuth()

#初始化Flask-HTTPAuth
@auth.verify_password
def verify_password(email_or_token,password):
    if email_or_token== '':
        return False
    if password=='':
        g.current_user = User.verify_auth_token(email_or_token)
        g.token_used = True
        return g.current_user is not None
    user = User.query.filter_by(email=email_or_token).first()
    if not user:
        return False
    g.current_user = user
    g.token_used = False
    return user.verify_password(password)

#Flask-HTTPAuth错误处理程序
@auth.error_handler
def auth_error():
    return unauthorized('invalid credetials')

#在before_request处理程序中验证身份
@api.before_request
@auth.login_required
def before_request():
    if not g.current_user.is_anonymous and not g.current_user.confirmed:
        return forbidden('Unconifrmed account')


#生成身份验证token
@api.route('/tokens/',methods=['POST'])
def get_token():
    #当前用户利用旧令牌登陆时，检查g.token_used的值，拒绝使用令牌验证身份，这样做是
    #为了防止用户绕过令牌机制，使用旧令牌请求新令牌
    if g.current_user.is_anonymous or g.token_used:
        return unauthorized('invalid credetials')
    return jsonify({'token':g.current_user.generate_auth_token(expiration=3600),'expiration':3600})
