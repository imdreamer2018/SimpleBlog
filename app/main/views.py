# from flask import render_template, session, redirect, url_for, current_app
# from .. import db
# from ..models import User
# from ..email import send_email
# from . import main
# from .forms import NameForm
#
#
# @main.route('/', methods=['GET', 'POST'])
# def index():
#     form = NameForm()
#     if form.validate_on_submit():
#         user = User.query.filter_by(username=form.name.data).first()
#         if user is None:
#             user = User(username=form.name.data)
#             db.session.add(user)
#             db.session.commit()
#             session['known'] = False
#             if current_app.config['FLASKY_ADMIN']:
#                 send_email(current_app.config['FLASKY_ADMIN'], 'New User',
#                            'mail/new_user', user=user)
#         else:
#             session['known'] = True
#         session['name'] = form.name.data
#         return redirect(url_for('.index'))
#     return render_template('index.html',
#                            form=form, name=session.get('name'),
#                            known=session.get('known', False))

from flask import render_template,flash,url_for,redirect,abort,request,current_app,make_response
from . import main
from ..models import User,Role,Permission,Post,Comment
from flask_login import login_required,current_user
from .forms import EditProfileForm,EditProfileAdminForm,PostForm,CommentForm
from app import db
from ..decorators import admin_required,permission_required
from flask_sqlalchemy import get_debug_queries

@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['FLASKY_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    return response

@main.route('/',methods=['GET','POST'])
def index():
    form = PostForm()
    if current_user.can(Permission.WRITE) and form.validate_on_submit():
        post = Post(body = form.body.data,author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('.index'))
    page = request.args.get('page',1,type=int)
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page,per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out = False)
    posts = pagination.items
    return render_template('index.html',form=form,posts=posts,show_followed=show_followed,pagination=pagination)

@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        abort(404)
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    return render_template('user.html',user=user,posts=posts)

@main.route('/edit-profile',methods=['GET','POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        #current_app._get_current_object()赋值给app作为当前程序的实例
        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('您的资料已更新！')
        return redirect(url_for('.user',username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html',form=form)


@main.route('/edit-profile/<int:id>',methods=['GET','POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        db.session.commit()
        flash('用户资料已更改!')
        return redirect(url_for('.user',username = user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role.id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html',form=form,user=user)

#为文章提供固定链接
@main.route('/post/<int:id>',methods=['GET','POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,post=post,author=current_user._get_current_object())
        db.session.add(comment)
        db.session.commit()
        flash('您已提交评论')
        return redirect(url_for('.post',id=post.id,page=-1))
    page = request.args.get('page',1,type=int)
    if page == -1:
        #得到最后一条评论所在的页数
        page = (post.comments.count() - 1) // current_app.config['FLASKY_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page,per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],error_out=False)
    comments = pagination.items
    return render_template('post.html',posts=[post],form=form,comments=comments,pagination=pagination)

#编辑博客文章路由
@main.route('/edit/<int:id>',methods=['GET','POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and not current_user.can(Permission.ADMIN):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        db.session.commit()
        flash('博客文章修改成功！')
        return redirect(url_for('.post',id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html',form=form)

#“关注”路由的视图函数
@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户名无效！')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('您已经关注他，无需再次关注！')
    current_user.follow(user)
    db.session.commit()
    flash('您已经关注了 %s.'% username)
    return redirect(url_for('.user',username=username))

#取消“关注”路由视图函数
@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户名无效')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('您没有关注他，无需取消关注！')
    current_user.unfollow(user)
    db.session.commit()
    flash('您已经取消了关注 %s.'% username)
    return redirect(url_for('.user',username=username))

#“粉丝s”路由视图函数
@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('无效的用户名')
        return redirect(url_for('.index'))
    page = request.args.get('page',1,type=int)
    pagination = user.followers.paginate(page,per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],error_out=False)
    follows = [{'user':item.follower,'timestamp':item.timestamp}
               for item in pagination.items]
    return render_template('followers.html',user=user,title="粉丝来自",
                           endpoint='.followers',pagination=pagination,
                           follows=follows)

#“关注s”路由视图
@main.route('/followed_by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('无效的用户名')
        return redirect(url_for('.index'))
    page = request.args.get('page',1,type=int)
    pagination = user.followed.paginate(page,per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="关注来自",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)

#查询所有文章还是所关注用户的文章
@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed','',max_age=30*24*60*60) #30天
    return resp

@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed','1',max_age=30*24*60*60)
    return resp

#管理评论的路由
@main.route('/moderate')
@login_required
@permission_required(Permission.MODERATE)
def moderate():
    page = request.args.get('page',1,type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page,per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html',comments=comments,pagination=pagination,page=page)

#评论管理路由
@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',page=request.args.get('page',1,type=int)))

@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('.moderate',page=request.args.get('page',1,type=int)))