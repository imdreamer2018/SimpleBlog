from werkzeug.security import generate_password_hash,check_password_hash
from flask_login import UserMixin,AnonymousUserMixin
from . import db,login_manager
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from flask import current_app,request,url_for
from datetime import datetime
from app.exceptions import ValidationError
import hashlib
from random import randint

'''
操作                          权限名             权限值
关注用户                      FOLLOW              1
在他人的文章中发表评论        COMMENT             2
写文章                        WRITE               4
管理他人发表的评论            MODERATE            8
管理员权限                    ADMIN               16  
'''
class Permission:
    FOLLOW = 1
    COMMENT = 2
    WRITE = 4
    MODERATE = 8
    ADMIN = 16

'''
用户角色            权限                                  说明
匿名                无                                    对应只读权限，这是未登录的未知用户
用户                FOLLOW,COMMENT,WRITE                  具有发布文章，发表评论和关注其他用户的权限，这是新用户的默认角色
协管者              FOLLOW,COMMENT,WRITE,MODERATE         增加管理其他用户所发表评论的权限
管理员              FOLLOW,COMMENT,WRITE,MODERATE,ADMIN   具有所有权限，包括修改其他用户所属角色的权限  
'''

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean,default=False,index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __init__(self,**kwargs):
        super(Role,self).__init__(**kwargs)
        if self.permissions is None:
            self.permissions = 0

    #增加权限
    def add_permission(self,perm):
        if not self.has_permission(perm):
            self.permissions +=perm

    #移除权限
    def remove_permission(self,perm):
        if self.has_permission(perm):
            self.permissions -= perm

    #重置权限为0
    def reset_permissions(self):
        self.permissions = 0

    #利用位与运算检查是否拥有权限
    def has_permission(self,perm):
        return self.permissions & perm == perm

    #静态方法，自动更新角色权限
    @staticmethod
    def insert_roles():
        roles = {
            'User':[Permission.FOLLOW,Permission.COMMENT,Permission.WRITE],
            'Moderator':[Permission.FOLLOW,Permission.COMMENT,Permission.WRITE,Permission.MODERATE],
            'Administrator':[Permission.FOLLOW,Permission.COMMENT,Permission.WRITE,Permission.MODERATE,Permission.ADMIN]
        }
        default_role = 'User'
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.reset_permissions()
            for perm in roles[r]:
                role.add_permission(perm)
            role.default = (role.name ==default_role)
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name

#关注关系中关联表的模型实现
class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True)
    followed_id = db.Column(db.Integer,db.ForeignKey('users.id'),primary_key=True)
    timestamp = db.Column(db.DateTime)

    def __init__(self,**kwargs):
        super(Follow,self).__init__(**kwargs)
        if self.timestamp is None:
            self.timestamp = datetime.now()

class User(UserMixin,db.Model):
    __tablename__ = 'users'
    #用户ID,电子邮箱，账户名，外键角色表ID，账户密码hash值，确认状态
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64),unique =True,index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean,default=False)

    #真实姓名，所在地区，关于我，注册时间，上次登陆时间
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime())
    last_seen = db.Column(db.DateTime(),default = datetime.now())

    #gravatar头像MD5散列值
    avatar_hash = db.Column(db.String(32))

    posts = db.relationship('Post',backref='author',lazy='dynamic')

    #被self关注的所有人
    followed = db.relationship('Follow',foreign_keys=[Follow.follower_id],
                               backref=db.backref('follower',lazy='joined'),
                               lazy='dynamic',cascade='all,delete-orphan')
    #关注self的所有人
    followers = db.relationship('Follow',foreign_keys=[Follow.followed_id],
                                backref=db.backref('followed',lazy='joined'),
                                lazy='dynamic',cascade='all,delete-orphan')

    #评论
    comments = db.relationship('Comment',backref='author',lazy='dynamic')

    def __init__(self,**kwargs):
        super(User,self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['FLASKY_ADMIN']:
                self.role = Role.query.filter_by(name='Administrator').first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = self.gravatar_hash()
        if self.member_since is None:
            self.member_since = datetime.utcnow()
        #把自己设为关注者
        self.follow(self)
    #检测并更新最后登陆时间
    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    #检测用户是否拥有权限
    def can(self,perm):
        return self.role is not None and self.role.has_permission(perm)

    #检测用户是否是管理员权限
    def is_administrator(self):
        return self.can(Permission.ADMIN)

    '''
    itsdangerous提供多种生成token的方法，其中TimedJSONWebSignatureSerializer类生成具有过期时间的JSON Web签名
    例如generate_confirmation_token方法，dumps()方法为指定的数据产生一个加密签名，然后对数据和签名进行序列化
    生成令牌字符串，为解码token，序列号对象提供了loads()方法，唯一参数为token字符串
    '''
    #产生确认状态邮件随机token，有效时间3600s
    def generate_confirmation_token(self,expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'],expiration)
        return s.dumps({'confirm':self.id}).decode('utf-8')
    #检验token是否正确
    def confirm(self,token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        if data.get('confirm') !=self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    #产生重置密码token
    def generate_reset_token(self,expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'],expiration)
        return s.dumps({'reset':self.id}).decode('utf-8')

    #检验重置密码token
    @staticmethod
    def reset_password(token,new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        user = User.query.get(data.get('reset'))
        if user is None:
            return False
        user.password = new_password
        db.session.add(user)
        return True

    #产生更改邮箱的token
    def generate_email_change_token(self,new_email,expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'],expiration)
        return s.dumps({'change_email':self.id,'new_email':new_email}).decode('utf-8')

    #检验更改邮箱token
    def change_email(self,token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token.encode('utf-8'))
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_hash = self.gravatar_hash()
        db.session.add(self)
        return True



    @property
    def password(self):
        raise AttributeError('用户密码为只读')

    @password.setter
    def password(self,password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self,password):
        return check_password_hash(self.password_hash,password)


    #产生Gravatar哈希值
    def gravatar_hash(self):
        return hashlib.md5(self.email.lower().encode('utf-8')).hexdigest()


    #生成Gravatar头像
    def gravatar(self,size=100,default='wavatar',rating='g'):
        g = {'1':'mm','2':'identicon','3':'monsterid','4':'wavatar','5':'retro'}
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = self.avatar_hash or self.gravatar_hash()
        default = g[str(randint(1,5))]
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(url=url,hash=hash,size=size,default=default,rating=rating)

    #self关注user
    def follow(self,user):
        if not self.is_following(user):
            f = Follow(follower=self,followed=user)
            db.session.add(f)

    #self取消关注self
    def unfollow(self,user):
        f = self.followed.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)

    #判断user是否被self关注
    def is_following(self,user):
        if user.id is None:
            return False
        return self.followed.filter_by(followed_id=user.id).first() is not None
    #判断user是否是self的粉丝
    def is_followed_by(self,user):
        if user.id is None:
            return False
        return self.followers.filter_by(follower_id=user.id).first() is not None

    #获取关注用户的文章
    @property
    def followed_posts(self):
        return Post.query.join(Follow,Follow.followed_id == Post.author_id).filter(Follow.follower_id == self.id)

    #把用户设为自己的关注者
    @staticmethod
    def add_self_follows():
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)
                db.session.add(user)
                db.session.commit()

    #所有用户关注admin
    @staticmethod
    def add_admin_follows():
        u = User.query.filter_by(username='admin').first()
        for user in User.query.all():
            if not user.is_following(u):
                user.follow(u)
                db.session.add(user)
                db.session.commit()

    #把用户转化成JSON格式的序列化字典
    def to_json(self):
        json_user = {
            'url':url_for('api.get_user',id=self.id),
            'username':self.username,
            'member_since':self.member_since,
            'last_seen':self.last_seen,
            'posts_url':url_for('api.get_user_posts',id=self.id),
            'followed_posts_url':url_for('api.get_user_followed_posts',id=self.id),
            'post_count':self.posts.count()
        }
        return json_user

    #支持基于token的身份验证
    def generate_auth_token(self,expiration):
        s = Serializer(current_app.config['SECRET_KEY'],expires_in=expiration)
        return s.dumps({'id':self.id}).decode('utf-8')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    def __repr__(self):
        return '<User %r>' % self.username

class AnonymousUser(AnonymousUserMixin):
    def can(self,permissions):
        return False

    def is_administrator(self):
        return False

login_manager.anonymous_user = AnonymousUser

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from markdown import markdown
import bleach

#文章字段
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer,primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime,index=True)
    author_id = db.Column(db.Integer,db.ForeignKey('users.id'))

    comments = db.relationship('Comment',backref='post',lazy='dynamic')

    def __init__(self,**kwargs):
        super(Post,self).__init__(**kwargs)
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    # 把文章转换成JSON格式的序列化字典
    def to_json(self):
        json_post={
            'url':url_for('api.get_post',id=self.id),
            'body':self.body,
            'body_html':self.body_html,
            'timestamp':self.timestamp,
            'author_url':url_for('api.get_user',id=self.author_id),
            'comments_url':url_for('api.get_post_comments',id=self.id),
            'comment_count':self.comments.count()
        }
        return json_post


    @staticmethod
    def from_json(json_post):
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post dose not have a body')
        return Post(body=body)

    '''
    定义静态方法，将传入的markdown文本转换为HTML
    allowed_tags为HTML标签白名单
    转换过程：
    1、markdown函数初步把Markdown文本转换成HTML
    2、把得到的结果和允许使用的HTML标签列表传给clean函数，clean()函数删除所有不在白名单中的标签
    3、最后一步由linkify()完成，把纯文本中的URL转换成合适的<a>链接。
    '''
    @staticmethod
    def on_change_body(target,value,oldvalue,initiator):
        attrs = {
            '*': ['class'],
            'a': ['href', 'rel'],
            'img': ['alt','src'],
        }
        allowed_tags = ['a','abbr','acronym','b','blockquote','code','img','src','alt','br',
                        'em','i','li','ol','pre','strong','ul','h1','h2','h3','p']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value,output_format='html'),tags=allowed_tags,strip=True,attributes=attrs,protocols=['http', 'https']))

#on_change_body()函数注册在body字段上，是SQLAlchemy "set"事件的监听程序，当body字段设了新值，这个函数就会自动调用
db.event.listen(Post.body,'set',Post.on_change_body)

#评论字段
class Comment(db.Model):
    __tablename = 'comments'
    id = db.Column(db.Integer,primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime,index=True)
    disabled = db.Column(db.Boolean)
    author_id = db.Column(db.Integer,db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer,db.ForeignKey('posts.id'))

    def __init__(self,**kwargs):
        super(Comment,self).__init__(**kwargs)
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_json(self):
        json_comment = {
            'url':url_for('api.get_comment',id=self.id),
            'post_url':url_for('api.get_post',id=self.post_id),
            'body':self.body,
            'body_html':self.body_html,
            'disabled':self.disabled,
            'timestamp':self.timestamp,
            'author_url':url_for('api.get_user',id=self.author_id)
        }
        return json_comment

    @staticmethod
    def from_json(json_comment):
        body = json_comment.get('body')
        if body is None or body=='':
            raise ValidationError('comment does not have body')
        return Comment(body=body)

    @staticmethod
    def on_changed_body(target,value,oldvalue,initiator):
        allowed_tags = ['a','abbr','acronym','b','code','em','i','strong','br']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value,output_format='html'),tags=allowed_tags,strip=True))

db.event.listen(Comment.body,'set',Comment.on_changed_body)

