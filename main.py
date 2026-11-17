# Importar
from flask import Flask, render_template, request, redirect
# Importando a biblioteca de banco de dados
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Conectando ao SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diary.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Criando um Banco de Dados (DB)
db = SQLAlchemy(app)


class Card(db.Model): # Criando a tabela do Banco de Dados
    id = db.Column(db.Integer, primary_key=True)  # id -> chave primária
    nome = db.Column(db.String(100), nullable=False)  # title -> string de até 100 caracteres, não pode ser nulo
    subtitle = db.Column(db.String(100), nullable=False)  # subtitle -> string de até 100 caracteres, não pode ser nulo
    text = db.Column(db.Text, nullable=False)  # text -> texto(255 caracteres) não pode ser nulo


# Executando a página com conteúdo
@app.route('/')
def index():
    return render_template("home.html")

