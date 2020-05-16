from . import api
from flask import jsonify,request,g,url_for,current_app
from ..models import Post,Permission
from .. import db
from .errors import forbidden
from .decorators import permission_required

'''
Flasky应用API资源
资源URL                       方法         说明
/posts/                       GET          返回所有博客文章
/posts/                       POST         创建一篇博客文章
/posts/<int:id>               GET          返回一篇博客文章
/posts/<int:id>               PUYT         修改一篇博客文章
'''

#获取文章集合
@api.route('/posts/')
def get_posts():
    page = request.args.get('page',1,type=int)
    pagination = Post.query.paginate(page,per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],error_out=False)
    posts = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_posts',page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_posts',page=page+1)
    return jsonify({'posts':[post.to_json() for post in posts],
                    'prev':prev,
                    'next':next,
                    'count':pagination.total})

#获取单篇文章博客
@api.route('/posts/<int:id>')
def get_post(id):
    post = Post.query.get_or_404(id)
    return jsonify(post.to_json())

#创建一篇文章博客
@api.route('/posts/<int:id>',methods=['POST'])
@permission_required(Permission.WRITE)
def new_post():
    post = Post.from_json(request.json)
    post.author = g.current_user
    db.session.add(post)
    db.session.commit()
    #返回201状态码，并把Location首部的值设为刚创建的这个资源的URL
    #为了方便客户端操作，相应的主体中包含了新建的资源
    return jsonify(post.to_json()), 201 ,{'Location':url_for('api.get_post',id=post.id)}

#修改一篇博客文章
@api.route('/posts/<int:id>',methods=['PUT'])
@permission_required(Permission.WRITE)
def edit_post(id):
    post = Post.query.get_or_404(id)
    if g.current_user != post.author and not g.current_user.can(Permission.ADMIN):
        return forbidden('Insufficient permissions')
    #如果request.json中没有'body'字段，则用post.body值为默认值
    post.body = request.json.get('body',post.body)
    db.session.add(post)
    db.session.commit()
    return jsonify(post.to_json())
