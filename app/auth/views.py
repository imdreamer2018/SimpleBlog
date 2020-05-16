from flask import render_template,redirect,request,url_for,flash
from flask_login import login_user,login_required,logout_user,current_user
from . import auth
from ..models import User
from .forms import LoginForm,RegistrationForm,ChangePasswordForm,ChangeEmailForm,PasswordResetForm,PasswordResetRequestForm
from app import db
from ..email import send_email


#登陆路由
@auth.route('/login',methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user,form.remember_me.data)
            next = request.args.get('index')
            if next is None or not next.startswith('/'):
                next = url_for('main.index')
            return redirect(next)
        flash('用户名或者密码错误')
    return render_template('auth/login.html',form=form)

#注销登陆路由
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已经退出登陆')
    return redirect(url_for('main.index'))

#注册账户路由
@auth.route('/register',methods=['GET','POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        token = user.generate_confirmation_token()
        send_email(user.email,'请确认您的账户','auth/email/confirm',user=user,token=token)
        flash('确认账户邮件已发送到您的邮箱，请登陆您的电子邮箱确认！')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html',form=form)

#确认邮箱路由
@auth.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirmed:
        return redirect(url_for('main.index'))
    if current_user.confirm(token):
        db.session.commit()
        flash('您已经确认了您的账户，谢谢！')
    else:
        flash('这个确认链接无效或者已经失效！')
    return redirect(url_for('main.index'))

'''
对于蓝本来说，before_request钩子只能应用到属于蓝本的请求上，
若想在蓝本中使用针对应用全局请求的钩子，必须使用before_app_request
同时满足以下3个条件时，before_app_request处理程序会拦截请求
1、用户已登陆(current_user.is_authenticated == True)
2、用户的账户还未确认
3、请求的URL不在身份验证蓝本中，而且也不是对静态文件的请求
如果请求满足以上条件，会被重定向到/auth/unconfirmed路由，显示一个确认账户相关信息的页面
'''
@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.ping()
    if current_user.is_authenticated and not current_user.confirmed \
        and request.blueprint !='auth' and request.endpoint !='static':
        return redirect(url_for('auth.unconfirmed'))

@auth.route('/unconfirmed')
def unconfirmed():
    if current_user.is_anonymous or current_user.confirmed:
        return redirect(url_for('main.index'))
    return render_template('auth/unconfirmed.html')

#重新发送确认邮件
@auth.route('confirm')
@login_required
def resend_confirmation():
    token = current_user.generate_confirmation_token()
    send_email(current_user.email, '请确认您的账户', 'auth/email/confirm', user=current_user, token=token)
    flash('确认账户邮件已发送到您的邮箱，请登陆您的电子邮箱确认！')
    return redirect(url_for('main.index'))

#更改密码路由
@auth.route('change-password',methods=['GET','POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.old_password.data):
            current_user.password = form.password.data
            db.session.add(current_user)
            db.session.commit()
            flash('您的密码已更改！')
            return redirect(url_for('main.index'))
        else:
            flash('密码错误！请重新输入')
    return render_template('auth/change_password.html',form=form)

#忘记密码，重置密码
@auth.route('reset',methods=['GET','POST'])
def password_reset_request():
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            send_email(user.email,'重置您的密码','auth/email/reset_password',user=user,token=token)
            flash('我们已向您发送一封电子邮件，其中包含重置密码的说明')
        else:
            flash('无效的电子邮箱，请重新输入！')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html',form=form)

@auth.route('reset/<token>',methods=['GET','POST'])
def password_reset(token):
    if not current_user.is_anonymous:
        return redirect(url_for('main.index'))
    form = PasswordResetForm()
    if form.validate_on_submit():
        if User.reset_password(token,form.password.data):
            db.session.commit()
            flash('密码重置成功')
            return redirect(url_for('auth.login'))
        else:
            return redirect(url_for('main.index'))
    return render_template('auth/reset_password.html',form=form)

@auth.route('change_email',methods=['GET','POST'])
@login_required
def change_email_request():
    form = ChangeEmailForm()
    if form.validate_on_submit():
        if current_user.verify_password(form.password.data):
            new_email = form.email.data
            token = current_user.generate_email_change_token(new_email)
            send_email(new_email,'请确认您的邮箱地址','auth/email/change_email',user=current_user,token=token)
            flash('我们已向您发送一封电子邮件，其中包含确认新电子邮件地址的说明')
            return redirect(url_for('main.index'))
        else:
            flash('邮箱已被注册或者密码错误！')
    return render_template('auth/change_email.html',form=form)

@auth.route('change_email<token>')
@login_required
def change_email(token):
    if current_user.change_email(token):
        db.session.commit()
        flash('恭喜您邮箱修改成功！')
    else:
        flash('请求错误！')
    return redirect(url_for('main.index'))
