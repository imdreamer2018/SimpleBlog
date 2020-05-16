from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField,TextAreaField,BooleanField,SelectField
from wtforms.validators import DataRequired,Length,Email,Regexp,ValidationError
from app.models import User,Role
from flask_pagedown.fields import PageDownField


class NameForm(FlaskForm):
    name = StringField('What is your name?', validators=[DataRequired()])
    submit = SubmitField('Submit')

#定义普通用户资料编辑表单
class EditProfileForm(FlaskForm):
    name = StringField('真实姓名',validators=[Length(0,64)])
    location = StringField('所在地址',validators=[Length(0,64)])
    about_me = TextAreaField('关于我')
    submit = SubmitField('提交')

#定义管理员用户编辑资料表单
class EditProfileAdminForm(FlaskForm):
    email = StringField('电子邮箱',validators=[DataRequired(),Length(1,64),Email()])
    username = StringField('用户名',validators=[
        DataRequired(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_]*$',0,'用户名必须仅由字母，数字和下划线组成')])
    confirmed = BooleanField('确认状态')
    role = SelectField('角色',coerce=int)
    name = StringField('真实姓名', validators=[Length(0, 64)])
    location = StringField('所在地址', validators=[Length(0, 64)])
    about_me = TextAreaField('关于我')
    submit = SubmitField('提交')

    def __init__(self,user,*args,**kwargs):
        super(EditProfileAdminForm,self).__init__(*args,**kwargs)
        self.role.choices = [(role.id,role.name)
                             for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_email(self,field):
        if field.data != self.user.email and User.query.filter_by(email = field.data).first():
            raise ValidationError('该电子邮箱已被注册，请重新输入！')

    def validate_username(self,field):
        if field.data != self.user.username and User.query.filter_by(username = field.data).first():
            raise ValidationError('该用户名已被注册，请重新输入！')


#博客文章表单
class PostForm(FlaskForm):
    body = PageDownField('想说点什么？',validators=[DataRequired()],render_kw={"placeholder":"支持Markdown格式文本"})
    submit = SubmitField('提交')

#评论输入表单
class CommentForm(FlaskForm):
    body = StringField('输入你的评论',validators=[DataRequired()])
    submit = SubmitField('评论')