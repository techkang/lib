from flask import render_template, redirect, url_for, abort, flash, request,\
    current_app, make_response
from flask_login import login_required, current_user
from flask_sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm,\
    CommentForm, QueryForm, AddForm, UserForm
from .. import db
from ..models import Permission, Role, User, Post, Comment, Book, Rent
from ..decorators import admin_required, permission_required


@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['FLASKY_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                'Slow query: %s\nParameters: %s\nDuration: %fs\nContext: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    return response


@main.route('/shutdown')
def server_shutdown():
    if not current_app.testing:
        abort(404)
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return 'Shutting down...'

@main.route('/', methods=['GET', 'POST'])
def index():
    form = QueryForm()
    if current_user.can(Permission.RENT) and \
            form.validate_on_submit():
#print(form.title.data)
        category=Book.title
        if form.category.data=='author':
            category=Book.author
        if form.category.data=='press':
            category=Book.press
        query= Book.query.filter(category.like('%'+'%'.join(form.title.data.split())+'%'))
        page = request.args.get('page', 1, type=int)
        pagination = query.paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('index.html', form=form, posts=posts, pagination=pagination)
    page = request.args.get('page', 1, type=int)
    query = Book.query
    pagination = query.order_by(Book.title.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('index.html', form=form, posts=posts, pagination=pagination)

@main.route('/rent/<book_id>')
@login_required
def rent(book_id):
    b=Book.query.filter_by(id=book_id).first()
    if (b.inventory<=0):
        flash("No enough book!")
        return redirect(url_for('.index'))
    b.inventory=b.inventory-1
    db.session.add(b)
    r=Rent(book_id=book_id,
            student_id=current_user.id)
    db.session.add(r)
    try:
        db.session.commit()
        flash("Congratualtions! You have rented the book")
    except:
        db.session.rollback()
        flash("Sorry, but you can't rent the book now")
    return redirect(url_for('.index'))

@main.route('/delete_book/<book_id>')
@login_required
@permission_required(Permission.DELETE)
def delete_book(book_id):
    b=Book.query.filter_by(id=book_id).first()
    if (b.inventory<=0):
        flash("No enough book!")
        return redirect(url_for('.index'))
    b.inventory=b.inventory-1
    db.session.add(b)
# db.session.add(r)
    try:
        db.session.commit()
        flash("Congratualtions! You have deleted the book")
    except:
        db.session.rollback()
        flash("Sorry, but you can't delete the book now")
    return redirect(url_for('.index'))

@main.route('/delete_all/<bookid>')
@login_required
@admin_required
def delete_all(bookid):
    rents=Rent.query.filter_by(book_id=bookid).all()
    for rent in rents:
        db.session.delete(rent)
    b=Book.query.filter_by(id=bookid).first()
    db.session.delete(b)
    try:
        db.session.commit()
        flash("Congratualtions! You have deleted the book")
    except:
        db.session.rollback()
        flash("Sorry, but you can't delete the book now")
    return redirect(url_for('.index'))
       
        
@main.route('/add_book',methods=['GET','POST'])
@login_required
@permission_required(Permission.INSERT)
def add_book():
   form = AddForm()
   if form.validate_on_submit():
       book=Book(title=form.title.data,       
               author=form.author.data,
               book_num=form.book_num.data,
               price=form.price.data,
               press=form.press.data,
               press_time=form.press_time.data,
               inventory=form.inventory.data)
       db.session.add(book)
       try:
           db.session.commit()
           flash('Congratulations! You have add new book.')
       except:
           db.session.rollback()
           flash('Sorry, but you failed to add new book.')       
   return render_template('add_book.html', form=form)


@main.route('/detail/<book_id>')
def detail(book_id):
    book=Book.query.filter_by(id=book_id).first_or_404()
    return render_template('detail.html',book=book, user=current_user)

@main.route('/user/<user_name>')
@login_required
def user(user_name):
    if not (current_user.username==user_name or current_user.can(Permission.INSERT)):
        abort(500)
    user = User.query.filter_by(username=user_name).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = Rent.query.filter_by(student_id=user.id).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('user.html', user=user, comments=comments,
                           pagination=pagination)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
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
        flash('The profile has been updated.')
        return redirect(url_for('.user', user_name=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        flash('Your comment has been published.')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) // \
            current_app.config['FLASKY_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form,
                           comments=comments, pagination=pagination)


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.RENT)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('You are already following this user.')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash('You are now following %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.RENT)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('You are not following this user.')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash('You are not following %s anymore.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followers of",
                           endpoint='.followers', pagination=pagination,
                           follows=follows)


@main.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('Invalid user.')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['FLASKY_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followed by",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30*24*60*60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30*24*60*60)
    return resp

@main.route('/return_book',methods=['POST','GET'])
@login_required
@permission_required(Permission.INSERT)
def return_book():
    form=UserForm()
    if form.validate_on_submit():   
        user=User.query.filter(User.username.like(form.username.data+'%')).first_or_404()
        return redirect(url_for('.user',user_name=user.username))
    page = request.args.get('page', 1, type=int)
    pagination = Rent.query.paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments,form=form,
                           pagination=pagination, page=page)

@main.route('/return_book_confirm/<int:book_id>__<int:student_id>')
@login_required
@permission_required(Permission.INSERT)
def return_book_confirm(book_id,student_id):
    logs=Rent.query.filter_by(book_id=book_id)
    log=logs.filter_by(student_id=student_id).first()
    db.session.delete(log)
    book=Book.query.filter_by(id=book_id).first()
    book.inventory+=1
    db.session.add(book)
    try:
        db.session.commit()
        flash("Congratulations! The book has been returned.")
    except:
        db.session.rollback()
        flash("Sorry, but it seems that you can not return book now.")
    return redirect(url_for('.return_book'))


@main.route('/moderate')
@login_required
@permission_required(Permission.INSERT)
def moderate():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('moderate.html', comments=comments,
                           pagination=pagination, page=page)


@main.route('/moderate/enable/<int:id>')
@login_required
@permission_required(Permission.INSERT)
def moderate_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/disable/<int:id>')
@login_required
@permission_required(Permission.INSERT)
def moderate_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('.moderate',
                            page=request.args.get('page', 1, type=int)))
