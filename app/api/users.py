from flask import jsonify,g,request,url_for,current_app
from . import api
from ..models import User,Post

'''
Flasky应用API资源
资源URL                       方法          说明
/users/                        GET          返回所有用户
/users/<int:id>                GET          返回一个用户
/users/<int:id>/posts/         GET          返回一个用户发布的所有文章
/users/<int:id>/timeline/      GET          返回一个用户所关注用户发布的所有文章
'''

@api.route('/users/')
def get_users():
    page = request.args.get('page',1,type=int)
    pagination = User.query.order_by(User.id.asc()).paginate(
        page,per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],error_out=False)
    users = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_users',page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_users',page=page+1)
    return jsonify({
        'users':[user.to_json() for user in users],
        'prev':prev,
        'next':next,
        'count':pagination.total
    })


@api.route('/users/<int:id>')
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify(user.to_json())

@api.route('/users/<int:id>/posts/')
def get_user_posts(id):
    user = User.query.get_or_404(id)
    page = request.args.get('page',1,type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page,per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_user_posts',id=id,page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_user_posts',id=id,page=page+1)
    return jsonify({
        'posts':[post.to_json() for post in posts],
        'prev':prev,
        'next':next,
        'count':pagination.total
    })

@api.route('/users/<int:id>/timeline/')
def get_user_followed_posts(id):
    user = User.query.get_or_404(id)
    page = request.args.get('page',1,type=int)
    pagination = user.followed_posts.order_by(Post.timestamp.desc()).paginate(
        page,per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_user_followed_posts',id=id,page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_user_followed_posts',id=id,page=page+1)
    return jsonify({
        'posts':[post.to_json() for post in posts],
        'prev':prev,
        'next':next,
        'count':pagination.total
    })