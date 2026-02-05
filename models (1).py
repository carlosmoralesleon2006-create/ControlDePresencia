from extensions import db, bcrypt, login_manager
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import time, datetime

# ----------------- Funciones de seguridad y login -----------------

@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario dado su ID. Flask-Login usa el ID único (PK) de Empleado."""
    return Empleado.query.get(int(user_id))

# ----------------- Modelos de la Base de Datos -----------------

class Empresa(db.Model):
    __tablename__ = 'empresa'
    id = db.Column(db.Integer, primary_key=True)
    cif = db.Column(db.String(15), unique=True, nullable=False)
    nombre_comercial = db.Column(db.String(100), nullable=False)
    domicilio = db.Column(db.String(255))
    localidad = db.Column(db.String(100))
    codigo_postal = db.Column(db.String(10))
    provincia = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telefono = db.Column(db.String(15))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    radio = db.Column(db.Float, default=50.0)

    empleados = db.relationship(
        'Empleado',
        backref='empresa_obj',
        lazy=True,
    )

    def __repr__(self):
        return f"<Empresa {self.nombre_comercial}>"


class Rol(db.Model):
    __tablename__ = 'rol'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)

    empleados = db.relationship(
        'Empleado',
        backref='rol_obj',
        lazy=True,
        foreign_keys='Empleado.id_rol'
    )

    def __repr__(self):
        return f"<Rol {self.nombre}>"


class Horario(db.Model):
    __tablename__ = 'horario'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)

    empleados = db.relationship(
        'Empleado',
        backref='horario_obj',
        lazy=True,
        foreign_keys='Empleado.id_horario'
    )

    franjas = db.relationship(
        'FranjaHoraria',
        backref='horario_obj',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Horario {self.nombre}>"


class FranjaHoraria(db.Model):
    __tablename__ = 'franja_horaria'
    id = db.Column(db.Integer, primary_key=True)

    id_horario = db.Column(db.Integer, db.ForeignKey('horario.id'), nullable=False)

    dia_semana = db.Column(db.SmallInteger, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('id_horario', 'dia_semana', 'hora_inicio', 'hora_fin', name='_horario_dia_inicio_fin_uc'),
    )

    def __repr__(self):
        return f"<FranjaHoraria {self.id_horario} Día:{self.dia_semana} {self.hora_inicio} - {self.hora_fin}>"


class Empleado(db.Model, UserMixin):
    __tablename__ = 'empleado'

    id = db.Column(db.Integer, primary_key=True)

    nif = db.Column(db.String(15), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(50), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    telefono = db.Column(db.String(15))

    domicilio = db.Column(db.String(255))
    localidad = db.Column(db.String(100))
    codigo_postal = db.Column(db.String(10))
    provincia = db.Column(db.String(100))

    id_empresa = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    id_rol = db.Column(db.Integer, db.ForeignKey('rol.id'), nullable=False)
    id_horario = db.Column(db.Integer, db.ForeignKey('horario.id'), nullable=False, default=1)

    password_hash = db.Column(db.String(255), nullable=False)

    def get_id(self):
        return str(self.id)

    @property
    def password(self):
        raise AttributeError('La contraseña no es un atributo de lectura.')

    @password.setter
    def password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Empleado {self.nombre} {self.apellidos} ({self.nif})>"


class Registro(db.Model):
    __tablename__ = 'registro'
    id_registro = db.Column(db.Integer, primary_key=True)
    hora_entrada = db.Column(db.DateTime)
    hora_salida = db.Column(db.DateTime)
    id_trabajador = db.Column(db.Integer, db.ForeignKey('empleado.id'), nullable=False)

class Incidencia(db.Model):
    __tablename__ = 'incidencia'
    id_incidencia = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)
    descripcion = db.Column(db.Text, nullable=False)
    id_trabajador = db.Column(db.Integer, db.ForeignKey('empleado.id'), nullable=False)