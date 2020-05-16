from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,BooleanField,SubmitField
from wtforms.validators import DataRequired,length,Email,Regexp,EqualTo
from wtforms import ValidationError
from ..models import User

#登陆表单
class LoginForm(FlaskForm):
    email = StringField('电子邮箱',validators=[DataRequired(),length(1,64),Email()])
    password = PasswordField('密码',validators=[DataRequired()])
    remember_me = BooleanField('记住我')
    submit = SubmitField('登陆')

#注册表单
class RegistrationForm(FlaskForm):
    email = StringField('电子邮箱',validators=[DataRequired(),length(1,64),Email()])
    username = StringField('用户名',validators=[
        DataRequired(),length(1,64),
        Regexp('^[A-Za-z][A-Za-z0-9_]*$',0,
               '用户名必须仅为多为字母，数字，或者下划线组成！')])
    password = PasswordField('密码',validators=[DataRequired(),EqualTo('password2',message='两次密码必须一样！')])
    password2= PasswordField('确认密码',validators=[DataRequired()])
    submit = SubmitField('注册')

    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('该邮箱已被注册，请重新输入！')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('该用户名已被注册，请重新输入！')

#修改密码表单，利用旧密码修改
class ChangePasswordForm(FlaskForm):
    old_password =PasswordField('旧密码',validators=[DataRequired()])
    password = PasswordField('新密码',validators=[DataRequired(),EqualTo('password2',message='重新输入的两次密码必须一致')])
    password2= PasswordField('确认新密码',validators=[DataRequired()])
    submit = SubmitField('更改密码')

#忘记旧密码，验证邮箱重置密码
class PasswordResetRequestForm(FlaskForm):
    email = StringField('请输入您的电子邮箱',validators=[DataRequired(),length(1,64),Email()])
    submit = SubmitField('发送邮件')

#已验证邮箱，重置密码表单
class PasswordResetForm(FlaskForm):
    password = StringField('新密码',validators=[DataRequired(),EqualTo('password2',message='两次输入密码必须一致')])
    password2= StringField('确认密码',validators=[DataRequired()])
    submit = SubmitField('重置密码')

#更改邮箱表单
class ChangeEmailForm(FlaskForm):
    email = StringField('新邮箱',validators=[DataRequired(),length(1,64),Email()])
    password = PasswordField('密码',validators=[DataRequired()])
    submit = SubmitField('更改邮箱')

    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('该邮箱已被注册，请重新输入')