from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime  # 新增导入
from pytz import timezone
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 设置时区
os.environ['TZ'] = 'Asia/Shanghai'

# 时区转换函数
def utc_to_local(utc_time):
    utc = timezone('UTC')
    local = timezone('Asia/Shanghai')
    return utc.localize(utc_time).astimezone(local)

# 自定义过滤器
@app.template_filter('local_time')
def local_time_filter(utc_time):
    return utc_to_local(utc_time).strftime('%Y-%m-%d %H:%M')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # 新增字段，标识是否为管理员
    avatar = db.Column(db.String(200), default='default_avatar.png')  # 头像文件名

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.now)  # 文章发布时间
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 外键关联用户
    author = db.relationship('User', backref=db.backref('posts', lazy=True))  # 定义关系


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.now)
    # 注册用户关联
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # 匿名用户信息
    guest_name = db.Column(db.String(80))
    # 文章关联
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'))  # 父评论ID
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)
    author = db.relationship('User', backref=db.backref('comments', lazy=True))
    post = db.relationship('Post', backref=db.backref('comments', lazy=True))

with app.app_context():
    db.create_all()
    # 创建默认管理员用户
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_password = generate_password_hash('admin123')  # 默认管理员密码
        admin_user = User(username='admin', password=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()


@app.route('/')
def index():
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
    else:
        user = None

    posts = Post.query.order_by(Post.date_posted.desc()).all()  # 查询所有文章，按发布时间倒序排列
    return render_template('index.html', username=session.get('user'), user=user, posts=posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('用户名已存在')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('注册成功，请登录')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user'] = username
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


@app.route('/admin')
def admin():
    if 'user' not in session:
        flash('请先登录')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash('无权访问')
        return redirect(url_for('index'))

    users = User.query.all()
    posts = Post.query.order_by(Post.date_posted.desc()).all()  # 查询所有文章
    return render_template('admin.html', users=users, posts=posts, user=user)


@app.route('/admin/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # 检查用户是否登录且是管理员
    if 'user' not in session:
        flash('请先登录')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash('无权访问')
        return redirect(url_for('index'))

    # 删除用户
    user_to_delete = User.query.get(user_id)
    if user_to_delete:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('用户已删除')
    else:
        flash('用户不存在')

    return redirect(url_for('admin'))


@app.route('/post/new', methods=['GET', 'POST'])
def new_post():
    if 'user' not in session:
        flash('请先登录')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']  # 获取富文本内容
        user = User.query.filter_by(username=session['user']).first()

        if not title or not content:
            flash('标题和内容不能为空')
            return redirect(url_for('new_post'))

        new_post = Post(title=title, content=content, author=user)
        db.session.add(new_post)
        db.session.commit()

        flash('文章已发表')
        return redirect(url_for('index'))

    return render_template('new_post.html')


@app.route('/admin/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user' not in session:
        flash('请先登录')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash('无权访问')
        return redirect(url_for('index'))

    post_to_delete = Post.query.get(post_id)
    if post_to_delete:
        db.session.delete(post_to_delete)
        db.session.commit()
        flash('文章已删除')
    else:
        flash('文章不存在')

    return redirect(url_for('admin'))

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    page = request.args.get('page', 1, type=int)
    per_page = 5  # 每页显示5条评论
    comments = Comment.query.filter_by(post_id=post_id)\
                            .order_by(Comment.date_posted.desc())\
                            .paginate(page=page, per_page=per_page)


    if request.method == 'POST':
        content = request.form.get('content')
        guest_name = request.form.get('guest_name', None)
        parent_id = request.form.get('parent_id', None)

        if not content:
            flash('评论内容不能为空')
            return redirect(url_for('post_detail', post_id=post_id))

        new_comment = Comment(
            content=content,
            post_id=post_id,
            guest_name=guest_name if not session.get('user') else None,
            user_id=User.query.filter_by(username=session.get('user')).first().id if session.get('user') else None,
            parent_id=parent_id
        )
        db.session.add(new_comment)
        db.session.commit()
        flash('评论已提交')
        return redirect(url_for('post_detail', post_id=post_id))

    return render_template('post_detail.html',
                         post=post,
                         comments=comments,
                         username=session.get('user'))


@app.route('/comment/delete/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if 'user' not in session:
        flash('请先登录')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash('无权访问')
        return redirect(url_for('index'))

    comment_to_delete = Comment.query.get(comment_id)
    if comment_to_delete:
        db.session.delete(comment_to_delete)
        db.session.commit()
        flash('评论已删除')
    else:
        flash('评论不存在')

    return redirect(url_for('post_detail', post_id=comment_to_delete.post_id))



if __name__ == '__main__':
    app.run(debug=True)