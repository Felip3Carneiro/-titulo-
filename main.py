# Importações
from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Chave secreta para uso de session
app.secret_key = 'my_top_secret_123'

# Configuração do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diary.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializando o banco
db = SQLAlchemy(app)


# -------------------------
# Tabela de Cards
# -------------------------
class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    subtitle = db.Column(db.String(300), nullable=False)
    text = db.Column(db.Text, nullable=False)
    user_email = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Card {self.id}>'


# -------------------------
# Cria a tabela User
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    xp = db.Column(db.Integer, nullable=False)
    dias = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<User {self.email}>'


# Iniciando página de conteúdo
@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        form_login = request.form['email']
        form_password = request.form['password']

        users_db = User.query.all()

        for user in users_db:
            if form_login == user.email and form_password == user.password:
                session['user_email'] = user.email
                return redirect('/index')

        return render_template('login.html', error='Tente novamente, email ou senha incorretos')

    return render_template('login.html')


@app.route('/reg', methods=['GET', 'POST'])
def reg():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            return render_template('registration.html', error="email já existente")

        # Cria o usuário
        user = User(email=email, password=password, xp=0, dias=0)
        db.session.add(user)
        db.session.commit()

        return redirect('/')

    return render_template('registration.html')


# Iniciando página de conteúdo
@app.route('/index')
def index():
    if session.get('user_email') == "admin@admin.com":
        cards = Card.query.order_by(Card.id).all()
    else:
        cards = Card.query.filter_by(user_email=session.get('user_email')).order_by(Card.id).all()  # noqa: E501
    return render_template('index.html', cards=cards)


# Iniciando página de cartão
@app.route('/card/<int:id>')
def card(id):
    card = Card.query.get(id)

    return render_template('card.html', card=card)


# Iniciando página de criação de cartão
@app.route('/create')
def create():
    return render_template('create_card.html')


@app.route('/delete/<int:id>')
def delete_card(id):
    # Removendo do Banco de Dados
    card = Card.query.get(id)
    db.session.delete(card)
    db.session.commit()
    return redirect('/index')


# Formulário de criação
@app.route('/form_create', methods=['GET', 'POST'])
def form_create():
    if request.method == 'POST':
        title = request.form['title']
        subtitle = request.form['subtitle']
        text = request.form['text']

        card = Card(title=title, subtitle=subtitle, text=text, user_email=session.get('user_email'))  # noqa: E501

        db.session.add(card)
        db.session.commit()
        return redirect('/index')
    else:
        return render_template('create_card.html')


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
