from dotenv import dotenv_values
from flask import Flask, request, url_for, redirect, render_template, jsonify, abort, make_response
from flask_login import UserMixin, LoginManager, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy

from queue_manager import QueueManager

USER = dotenv_values().get("POSTGRES_USER")
PASSWORD = dotenv_values().get("POSTGRES_PASSWORD")

DATABASE_URI = f'postgresql://{USER}:{PASSWORD}@localhost/PostgresDb'

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config['SECRET_KEY'] = 'DNFLSH454T8_3RR3RNIW_EERJENR'

app.debug = True

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.init_app(app)

user_queue_manager = QueueManager('user_queue')
ticket_queue_manager = QueueManager('ticket_queue')

user_ticket_association = db.Table(
    'user_ticket_association',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('ticket_id', db.Integer, db.ForeignKey('ticket.id'), primary_key=True)
)


class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    tickets = db.relationship('Ticket', secondary=user_ticket_association, backref=db.backref('users', lazy='dynamic'))


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), unique=True, nullable=False)
    rows = db.Column(db.Integer, nullable=False)
    columns = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False)


db.init_app(app)

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = Users()
        user.username = request.form.get("username")
        user.password = request.form.get("password")

        db.session.add(user)
        db.session.commit()
        # Once user account created, automatically log them in
        login_user(user)
        return redirect(url_for("login"))
    return render_template("sign_up.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Users.query.filter_by(
            username=request.form.get("username")).first()
        if user.password == request.form.get("password"):
            login_user(user)
            return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/")
def home():
    return render_template("home.html")


@app.route('/user_tickets/<int:user_id>')
def user_tickets(user_id):
    user = Users.query.get(user_id)

    if user:
        user_tickets = user.tickets
        return render_template('user_tickets.html', user_tickets=user_tickets)
    else:
        return "Користувач не знайден"


@app.route('/api/users', methods=['GET'])
def get_users():
    users = Users.query.all()
    return jsonify({'users': [{'id': user.id, 'username': user.username} for user in users]})


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = Users.query.get(user_id)
    if not user:
        abort(404)
    return jsonify({'user': {'id': user.id, 'username': user.username}})


@app.route('/api/users', methods=['POST'])
def create_user():
    if not request.json or 'username' not in request.json or 'password' not in request.json:
        abort(400)
    username = request.json['username']
    password = request.json['password']
    user = Users()
    user.username = username
    user.password = password
    db.session.add(user)
    db.session.commit()
    user_queue_manager.send_message(f'User created: {username}')
    return jsonify({'user': {'id': user.id, 'username': user.username}}), 201


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = Users.query.get(user_id)
    if not user:
        abort(404)
    if not request.json:
        abort(400)
    if 'username' in request.json:
        user.username = request.json['username']
    if 'password' in request.json:
        user.password = request.json['password']
    db.session.commit()
    return jsonify({'user': {'id': user.id, 'username': user.username}})


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = Users.query.get(user_id)
    if not user:
        abort(404)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'result': True})

@app.route('/api/tickets', methods=['GET'])
def get_tickets():
    tickets = Ticket.query.all()
    return jsonify({'tickets': [{'id': ticket.id, 'title': ticket.title} for ticket in tickets]})


@app.route('/api/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        abort(404)
    return jsonify({'ticket': {'id': ticket.id, 'title': ticket.title}})


@app.route('/api/tickets', methods=['POST'])
def create_ticket():
    if not request.json or 'title' not in request.json or 'rows' not in request.json or 'columns' not in request.json or 'date' not in request.json:
        abort(400)
    title = request.json['title']
    rows = request.json['rows']
    columns = request.json['columns']
    date = request.json['date']
    user_id = request.json['user_id']

    user = Users.query.get(user_id)
    if user:
        ticket = Ticket(title=title, rows=rows, columns=columns, date=date)
        user.tickets.append(ticket)
        db.session.add(ticket)
        db.session.commit()
        ticket_queue_manager.send_message(f'Ticket created: {title}')
        return jsonify({'ticket': {'id': ticket.id, 'title': ticket.title}}), 201


@app.route('/api/tickets/<int:ticket_id>', methods=['PUT'])
def update_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        abort(404)
    if not request.json:
        abort(400)
    if 'title' in request.json:
        ticket.title = request.json['title']
    if 'rows' in request.json:
        ticket.rows = request.json['rows']
    if 'columns' in request.json:
        ticket.columns = request.json['columns']
    if 'date' in request.json:
        ticket.date = request.json['date']
    db.session.commit()
    return jsonify({'ticket': {'id': ticket.id, 'title': ticket.title}})


@app.route('/api/tickets/<int:ticket_id>', methods=['DELETE'])
def delete_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        abort(404)
    db.session.delete(ticket)
    db.session.commit()
    return jsonify({'result': True})


@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


if __name__ == '__main__':
    app.run()
