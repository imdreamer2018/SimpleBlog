from flask import request,jsonify,g,current_app,url_for
from . import api
from .. import db
from ..models import Comment,Post,Permission
from .decorators import permission_required

'''
Flasky应用API资源
资源URL                       方法         说明
/posts/<int:id>/comments/     GET          返回一篇博客的评论
/posts/<int:id>/comments/     POST         在一篇博客下添加一条评论
/comments/                    GET          返回所有评论
/comments/<int:id>            GET          返回一条评论
/comments/<int:id>/enable/    GET          对一条评论开放
/comments/<int:id>/disable/   GET          对一条评论禁用
'''

@api.route('/comments/')
def get_comments():
    page = request.args.get('page',1,type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page,per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],error_out=False)
    comments = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_comments',page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_comments',page=page+1)
    return jsonify({
        'comments':[comment.to_json() for comment in comments],
        'prev':prev,
        'next':next,
        'count':pagination.total})

@api.route('/comments/<int:id>')
def get_comment(id):
    comment = Comment.query.get_or_404(id)
    return jsonify(comment.to_json())

@api.route('/posts/<int:id>/comments/')
def get_post_comments(id):
    post = Post.query.get_or_404(id)
    page = request.args.get('page',1,type=int)
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page,per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],error_out=False)
    comments = pagination.items
    prev = None
    if pagination.has_prev:
        prev = url_for('api.get_posts_comments',id=id,page=page-1)
    next = None
    if pagination.has_next:
        next = url_for('api.get_posts_comments',id=id,page=page+1)
    return jsonify({
        'comments':[comment.to_json() for comment in comments],
        'prev':prev,
        'next':next,
        'count':pagination.total
    })

@api.route('/posts/<int:id>/comments/',methods=['POST'])
@permission_required(Permission.COMMENT)
def new_post_comment(id):
    post = Post.query.get_or_404(id)
    comment = Comment.from_json(request.json)
    comment.author = g.current_user
    comment.post = post
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_json()),201,{'Location':url_for('api.get_comment',id=comment.id)}

@api.route('/comments/<int:id>/enable/')
@permission_required(Permission.MODERATE)
def comment_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_json())

@api.route('/comments/<int:id>/disable/')
@permission_required(Permission.MODERATE)
def comment_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment.to_json())