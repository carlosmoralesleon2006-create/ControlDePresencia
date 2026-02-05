from flask import Blueprint, render_template, url_for, flash, redirect, request
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import UnmappedInstanceError
from datetime import time, datetime, timedelta
from sqlalchemy import or_

from extensions import db
from models import Empleado, Rol, Horario, FranjaHoraria, Empresa, Registro

main_bp = Blueprint('main', __name__)


def requires_superadmin():
    if not current_user.is_authenticated:
        flash('Necesitas iniciar sesión para acceder.', 'warning')
        return redirect(url_for('main.login'))

    rol_nombre = current_user.rol_obj.nombre if current_user.rol_obj else ''

    if rol_nombre != 'Superadministrador':
        flash('Acceso restringido. Esta sección solo es para Superadministradores.', 'danger')
        return redirect(url_for('main.index'))
    return None


def requires_admin_or_superadmin():
    if not current_user.is_authenticated:
        flash('Necesitas iniciar sesión para acceder.', 'warning')
        return redirect(url_for('main.login'))

    rol_nombre = current_user.rol_obj.nombre if current_user.rol_obj else ''

    if rol_nombre not in ['Administrador', 'Superadministrador']:
        flash('Acceso restringido. Esta sección es solo para personal de gestión.', 'danger')
        return redirect(url_for('main.index'))
    return None


@main_bp.route('/')
@main_bp.route('/index')
def index():
    return render_template('index.html', title='Dashboard')


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        nif = request.form.get('nif')
        password = request.form.get('password')

        user = Empleado.query.filter_by(nif=nif).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'¡Bienvenido, {user.nombre}!', 'success')

            next_page = request.args.get('next')

            if user.rol_obj and user.rol_obj.nombre in ['Administrador', 'Superadministrador']:
                return redirect(next_page or url_for('main.gestion_empresa'))
            else:
                return redirect(next_page or url_for('main.index'))
        else:
            flash('Fallo en el inicio de sesión. Revisa tu NIF y contraseña.', 'danger')

    return render_template('login.html', title='Iniciar Sesión')


@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado tu sesión.', 'info')
    return redirect(url_for('main.login'))


@main_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    rol_empleado = Rol.query.filter_by(nombre='Empleado').first()
    empresas_disponibles = Empresa.query.all()

    if not rol_empleado or not empresas_disponibles:
        flash('El registro está deshabilitado. No hay roles de "Empleado" o empresas configuradas.', 'danger')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        nif = request.form.get('nif').strip()
        nombre = request.form.get('nombre').strip()
        apellidos = request.form.get('apellidos').strip()
        password = request.form.get('password')
        email = request.form.get('email').strip()
        id_empresa = request.form.get('id_empresa', type=int)

        if not all([nif, nombre, apellidos, password, email, id_empresa]):
            flash('Faltan campos obligatorios para el registro.', 'danger')
            return render_template('registro.html', title='Registro', empresas=empresas_disponibles)

        if Empleado.query.filter_by(nif=nif).first():
            flash(f'Error: Ya existe un usuario con el NIF {nif}.', 'danger')
            return render_template('registro.html', title='Registro', empresas=empresas_disponibles)

        try:
            nuevo_empleado = Empleado(
                nif=nif,
                nombre=nombre,
                apellidos=apellidos,
                email=email,
                id_rol=rol_empleado.id,
                id_empresa=id_empresa,
                id_horario=1,
                password=password
            )
            db.session.add(nuevo_empleado)
            db.session.commit()

            flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('main.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error durante el registro: {e}', 'danger')

    return render_template('registro.html', title='Registro', empresas=empresas_disponibles)


# --- Rutas de Gestión de Empresas ---

@main_bp.route('/gestion_empresas', methods=['GET'])
@login_required
def gestion_empresas():
    superadmin_check = requires_superadmin()
    if superadmin_check:
        return superadmin_check

    empresas = Empresa.query.all()
    return render_template('gestion_empresas.html', title='Gestión de Empresas', empresas=empresas)


@main_bp.route('/empresa/nuevo', methods=['POST'])
@login_required
def empresa_nuevo():
    superadmin_check = requires_superadmin()
    if superadmin_check:
        return superadmin_check

    cif = request.form.get('cif').strip()
    nombre = request.form.get('nombre_comercial').strip()

    if not cif or not nombre:
        flash('El CIF y el Nombre Comercial son obligatorios.', 'danger')
        return redirect(url_for('main.gestion_empresas'))

    try:
        nueva_empresa = Empresa(
            cif=cif,
            nombre_comercial=nombre,
            domicilio=request.form.get('domicilio'),
            localidad=request.form.get('localidad'),
            codigo_postal=request.form.get('codigo_postal'),
            provincia=request.form.get('provincia'),
            email=request.form.get('email'),
            telefono=request.form.get('telefono'),
        )
        db.session.add(nueva_empresa)
        db.session.commit()
        flash(f'Empresa "{nombre}" creada con éxito.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Error: Ya existe una empresa con ese CIF.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear la empresa: {e}', 'danger')

    return redirect(url_for('main.gestion_empresas'))


@main_bp.route('/empresa/modificar/<int:empresa_id>', methods=['POST'])
@login_required
def empresa_modificar(empresa_id):
    superadmin_check = requires_superadmin()
    if superadmin_check:
        return superadmin_check

    empresa = Empresa.query.get_or_404(empresa_id)

    cif_nuevo = request.form.get('cif').strip()
    nombre_nuevo = request.form.get('nombre_comercial').strip()

    if not cif_nuevo or not nombre_nuevo:
        flash('El CIF y el Nombre Comercial son obligatorios.', 'warning')
        return redirect(url_for('main.gestion_empresas'))

    try:
        cif_existente = Empresa.query.filter(Empresa.cif == cif_nuevo, Empresa.id != empresa_id).first()
        if cif_existente:
             flash('Error: Ya existe otra empresa con ese CIF.', 'danger')
             return redirect(url_for('main.gestion_empresas'))

        empresa.cif = cif_nuevo
        empresa.nombre_comercial = nombre_nuevo
        empresa.domicilio = request.form.get('domicilio')
        empresa.localidad = request.form.get('localidad')
        empresa.codigo_postal = request.form.get('codigo_postal')
        empresa.provincia = request.form.get('provincia')
        empresa.email = request.form.get('email')
        empresa.telefono = request.form.get('telefono')

        db.session.commit()
        flash('Empresa actualizada con éxito.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al guardar los datos de la empresa: {e}', 'danger')

    return redirect(url_for('main.gestion_empresas'))


@main_bp.route('/empresa/eliminar/<int:empresa_id>', methods=['POST'])
@login_required
def empresa_eliminar(empresa_id):
    superadmin_check = requires_superadmin()
    if superadmin_check:
        return superadmin_check

    empresa = Empresa.query.get_or_404(empresa_id)


    empleados_asociados = Empleado.query.filter_by(id_empresa=empresa.id).count()
    if empleados_asociados > 0:
        flash(f'Error: La empresa "{empresa.nombre_comercial}" no se puede eliminar porque tiene {empleados_asociados} empleados asociados.', 'danger')
        return redirect(url_for('main.gestion_empresas'))

    try:
        db.session.delete(empresa)
        db.session.commit()
        flash(f'Empresa "{empresa.nombre_comercial}" eliminada con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la empresa: {e}', 'danger')

    return redirect(url_for('main.gestion_empresas'))


@main_bp.route('/gestion_empresa', methods=['GET', 'POST'])
@login_required
def gestion_empresa():

    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    if not current_user.id_empresa:
        if current_user.rol_obj.nombre == 'Superadministrador':
            flash('Como Superadministrador, gestionas todas las empresas. No tienes una empresa individual de configuración.', 'info')
            return redirect(url_for('main.gestion_empresas'))
        else:
            flash('Error: Tu cuenta de Administrador no está vinculada a ninguna empresa.', 'danger')
            return redirect(url_for('main.index'))

    empresa = current_user.empresa_obj

    if not empresa:
        flash('Error: El usuario no está asociado a ninguna empresa.', 'danger')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        cif_nuevo = request.form.get('cif')
        nombre_comercial_nuevo = request.form.get('nombre_comercial')
        domicilio = request.form.get('domicilio')
        localidad = request.form.get('localidad')
        codigo_postal = request.form.get('codigo_postal')
        provincia = request.form.get('provincia')
        email = request.form.get('email')
        telefono = request.form.get('telefono')
        empresa.lat = request.form.get('lat', type=float)
        empresa.lng = request.form.get('lng', type=float)
        empresa.radio = request.form.get('radio', type=float)

        if not cif_nuevo or not nombre_comercial_nuevo:
            flash('El CIF y el Nombre Comercial son obligatorios.', 'warning')
            return redirect(url_for('main.gestion_empresa'))

        try:
            cif_existente = Empresa.query.filter(Empresa.cif == cif_nuevo, Empresa.id != empresa.id).first()
            if cif_existente:
                 flash('Error: Ya existe otra empresa con ese CIF.', 'danger')
                 return redirect(url_for('main.gestion_empresa'))

            empresa.cif = cif_nuevo
            empresa.nombre_comercial = nombre_comercial_nuevo
            empresa.domicilio = domicilio
            empresa.localidad = localidad
            empresa.codigo_postal = codigo_postal
            empresa.provincia = provincia
            empresa.email = email
            empresa.telefono = telefono

            db.session.commit()
            flash('Información de la empresa actualizada con éxito.', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar los datos de la empresa: {e}', 'danger')

        return redirect(url_for('main.gestion_empresa'))

    return render_template('gestion_empresa.html', title='Gestión de Empresa', empresa=empresa)

# --- Rutas de Gestión de Roles ---

@main_bp.route('/gestion_roles')
@login_required
def gestion_roles():
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    roles = Rol.query.all()
    return render_template('gestion_roles.html', title='Gestión de Roles', roles=roles)


@main_bp.route('/rol/nuevo', methods=['POST'])
@login_required
def rol_nuevo():
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    rol_id = request.form.get('rol_id', type=int) # Intenta obtener el ID como entero
    nombre = request.form.get('nombre').strip()

    if not nombre:
        flash('El nombre del rol no puede estar vacío.', 'danger')
        return redirect(url_for('main.gestion_roles'))

    if rol_id:
        rol = Rol.query.get_or_404(rol_id)

        rol_existente = Rol.query.filter(Rol.nombre == nombre, Rol.id != rol_id).first()
        if rol_existente:
            flash(f'Error: Ya existe otro rol con el nombre "{nombre}".', 'danger')
            return redirect(url_for('main.gestion_roles'))

        try:
            rol.nombre = nombre
            db.session.commit()
            flash(f'Rol modificado a "{nombre}" con éxito.', 'success')
            return redirect(url_for('main.gestion_roles'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al modificar el rol: {e}', 'danger')
            return redirect(url_for('main.gestion_roles'))

    else:
        rol_existente = Rol.query.filter_by(nombre=nombre).first()
        if rol_existente:
            flash(f'Error: Ya existe un rol con el nombre "{nombre}".', 'danger')
            return redirect(url_for('main.gestion_roles'))

        try:
            nuevo_rol = Rol(nombre=nombre)
            db.session.add(nuevo_rol)
            db.session.commit()
            flash(f'Rol "{nombre}" creado con éxito.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el rol: {e}', 'danger')

    return redirect(url_for('main.gestion_roles'))

@main_bp.route('/rol/eliminar/<int:rol_id>', methods=['POST'])
@login_required
def rol_eliminar(rol_id):
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    rol = Rol.query.get_or_404(rol_id)

    empleados_asociados = Empleado.query.filter_by(id_rol=rol.id).count()
    if empleados_asociados > 0:
        flash(f'Error: El rol "{rol.nombre}" no se puede eliminar porque tiene {empleados_asociados} empleados asociados.', 'danger')
        return redirect(url_for('main.gestion_roles'))

    try:
        db.session.delete(rol)
        db.session.commit()
        flash(f'Rol "{rol.nombre}" eliminado con éxito.', 'success')
    except UnmappedInstanceError:
        flash('Error: El rol que intentas eliminar ya no existe.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el rol: {e}', 'danger')

    return redirect(url_for('main.gestion_roles'))

# --- Rutas de Gestión de Empleados ---

@main_bp.route('/gestion_empleados', methods=['GET', 'POST'])
@login_required
def gestion_empleados():
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    es_superadmin = current_user.rol_obj.nombre == 'Superadministrador'

    if es_superadmin:
        empleados = Empleado.query.all()
        empresas_disponibles = Empresa.query.all()
    else:
        empresa_id_actual = current_user.id_empresa
        empleados = Empleado.query.filter_by(id_empresa=empresa_id_actual).all()
        empresas_disponibles = Empresa.query.filter_by(id=empresa_id_actual).all()

    roles = Rol.query.all()

    horarios_disponibles = Horario.query.all()

    horario_default = Horario.query.get(1)

    if not horario_default:
        flash('ADVERTENCIA: No existe el Horario por defecto (ID=1). Por favor, créalo.', 'warning')

    empleado_editar = None
    nif_editar = request.args.get('nif_editar')
    if nif_editar:
        empleado_editar = Empleado.query.filter_by(nif=nif_editar).first()

    return render_template('gestion_empleados.html',
                           title='Gestión de Empleados',
                           empleados=empleados,
                           roles=roles,
                           horario_default=horario_default,
                           empleado_editar=empleado_editar,
                           empresas_disponibles=empresas_disponibles,
                           es_superadmin=es_superadmin,
                           horarios_disponibles=horarios_disponibles)

@main_bp.route('/empleado/nuevo', methods=['POST'])
@login_required
def empleado_nuevo():
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    nif = request.form.get('nif').strip()
    nombre = request.form.get('nombre').strip()
    apellidos = request.form.get('apellidos').strip()
    password = request.form.get('password')
    email = request.form.get('email').strip()
    telefono = request.form.get('telefono').strip()
    id_rol = request.form.get('id_rol', type=int)
    id_empresa_form = request.form.get('id_empresa', type=int)
    id_horario = request.form.get('id_horario', type=int)

    es_superadmin = current_user.rol_obj.nombre == 'Superadministrador'

    if es_superadmin and id_empresa_form:
        empresa_id = id_empresa_form
    elif not es_superadmin:
        empresa_id = current_user.id_empresa
    else:
        flash('Error: La empresa de destino no fue especificada.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    rol_elegido = Rol.query.get(id_rol)
    if not es_superadmin and rol_elegido.nombre != 'Empleado':
        flash('Acceso denegado: Solo los Superadministradores pueden asignar roles de Administrador o Superadministrador.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    if not all([nif, nombre, apellidos, password, email, id_rol]):
        flash('Faltan campos obligatorios para el nuevo empleado.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    if Empleado.query.filter_by(nif=nif).first():
        flash(f'Error: Ya existe un empleado con el NIF {nif}.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    if Empleado.query.filter_by(email=email).first():
        flash(f'Error: Ya existe un empleado con el email {email}.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    if not id_horario:
        id_horario = 1

    try:
        nuevo_empleado = Empleado(
            nif=nif,
            nombre=nombre,
            apellidos=apellidos,
            email=email,
            telefono=telefono,
            id_rol=id_rol,
            id_empresa=empresa_id,
            id_horario=id_horario,
            password=password
        )
        db.session.add(nuevo_empleado)
        db.session.commit()
        flash(f'Empleado {nombre} {apellidos} (NIF: {nif}) creado con éxito.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear el empleado: {e}', 'danger')

    return redirect(url_for('main.gestion_empleados'))


@main_bp.route('/empleado/modificar/<string:nif_original>', methods=['POST'])
@login_required
def empleado_modificar(nif_original):
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    empleado = Empleado.query.filter_by(nif=nif_original).first_or_404()

    es_superadmin = current_user.rol_obj.nombre == 'Superadministrador'

    if not es_superadmin and empleado.id_empresa != current_user.id_empresa:
        flash('Acceso denegado: No puedes modificar empleados de otras empresas.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    nif_nuevo = request.form.get('nif').strip()
    password_nuevo = request.form.get('password')
    id_rol = request.form.get('id_rol', type=int)
    id_empresa_form = request.form.get('id_empresa', type=int)
    id_horario = request.form.get('id_horario', type=int) # Capturar el horario seleccionado

    if es_superadmin and id_empresa_form:
        empleado.id_empresa = id_empresa_form

    rol_elegido = Rol.query.get(id_rol)
    rol_actual_empleado = empleado.rol_obj.nombre

    if not es_superadmin:
        if rol_actual_empleado != 'Empleado':
            flash('Acceso denegado: Un Administrador no puede modificar otros perfiles de gestión.', 'danger')
            return redirect(url_for('main.gestion_empleados'))

        if rol_elegido.nombre != 'Empleado':
            flash('Acceso denegado: Un Administrador solo puede asignar el rol "Empleado".', 'danger')
            return redirect(url_for('main.gestion_empleados'))


    if nif_nuevo != nif_original:
        if Empleado.query.filter(Empleado.nif == nif_nuevo).first():
            flash(f'Error: El NIF {nif_nuevo} ya está en uso en el sistema.', 'danger')
            return redirect(url_for('main.gestion_empleados', nif_editar=nif_original))

    try:
        empleado.nif = nif_nuevo
        empleado.nombre = request.form.get('nombre').strip()
        empleado.apellidos = request.form.get('apellidos').strip()
        empleado.email = request.form.get('email').strip()
        empleado.telefono = request.form.get('telefono').strip()
        empleado.id_rol = id_rol

        empleado.id_horario = id_horario

        if password_nuevo:
            empleado.password = password_nuevo
            flash('Contraseña del empleado actualizada.', 'info')

        db.session.commit()
        flash(f'Empleado {empleado.nombre} modificado con éxito.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al modificar el empleado: {e}', 'danger')

    return redirect(url_for('main.gestion_empleados'))



@main_bp.route('/empleado/eliminar/<string:nif>', methods=['POST'])
@login_required
def empleado_eliminar(nif):
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    empleado = Empleado.query.filter_by(nif=nif).first_or_404()

    if current_user.rol_obj.nombre != 'Superadministrador' and empleado.id_empresa != current_user.id_empresa:
        flash('Acceso denegado: No puedes eliminar empleados de otras empresas.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    if empleado.id == current_user.id:
        flash('No puedes eliminar tu propia cuenta de administrador.', 'danger')
        return redirect(url_for('main.gestion_empleados'))

    try:
        db.session.delete(empleado)
        db.session.commit()
        flash(f'Empleado {empleado.nombre} eliminado con éxito.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el empleado: {e}', 'danger')

    return redirect(url_for('main.gestion_empleados'))

# --- Rutas de Gestión de Horarios ---

@main_bp.route('/gestion_horarios')
@login_required
def gestion_horarios():
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    horarios = Horario.query.all()
    dias = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes', 6: 'Sábado', 7: 'Domingo'}

    horario_seleccionado = None
    horario_id = request.args.get('horario_id', type=int)
    if horario_id:
        horario_seleccionado = Horario.query.get(horario_id)

    return render_template('gestion_horarios.html',
                           title='Gestión de Horarios',
                           horarios=horarios,
                           dias=dias,
                           horario_seleccionado=horario_seleccionado)


def check_solapamiento(horario_id, dia_semana, hora_inicio, hora_fin, franja_id=None):

    try:
        t_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
        t_fin = datetime.strptime(hora_fin, '%H:%M').time()
    except ValueError:
        return "Formato de hora inválido (debe ser HH:MM)."

    if t_inicio >= t_fin:
        return "La hora de inicio debe ser anterior a la hora de fin."

    query = FranjaHoraria.query.filter(
        FranjaHoraria.id_horario == horario_id,
        FranjaHoraria.dia_semana == dia_semana
    )

    if franja_id:
        query = query.filter(FranjaHoraria.id != franja_id)

    franjas_existentes = query.all()

    for franja in franjas_existentes:
        existente_inicio = franja.hora_inicio
        existente_fin = franja.hora_fin

        solapamiento = (t_inicio < existente_fin) and (t_fin > existente_inicio)

        if solapamiento:
            return f"Se solapa con la franja existente: {franja.hora_inicio.strftime('%H:%M')} - {franja.hora_fin.strftime('%H:%M')}."

    return None

@main_bp.route('/horario/nuevo', methods=['POST'])
@login_required
def horario_nuevo():
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    horario_id = request.form.get('horario_id')
    nombre = request.form.get('nombre').strip()

    if not nombre:
        flash('El nombre del horario no puede estar vacío.', 'danger')
        return redirect(url_for('main.gestion_horarios'))

    if horario_id and horario_id.isdigit():
        horario = Horario.query.get(int(horario_id))

        if not horario:
            flash('Error: El horario a modificar no existe.', 'danger')
            return redirect(url_for('main.gestion_horarios'))

        horario_existente = Horario.query.filter(Horario.nombre == nombre, Horario.id != int(horario_id)).first()
        if horario_existente:
            flash(f'Error: Ya existe otro horario con el nombre "{nombre}".', 'danger')
            return redirect(url_for('main.gestion_horarios'))

        try:
            horario.nombre = nombre
            db.session.commit()
            flash(f'Horario "{nombre}" modificado con éxito.', 'success')
            return redirect(url_for('main.gestion_horarios'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al modificar el horario: {e}', 'danger')
            return redirect(url_for('main.gestion_horarios'))

    else:
        horario_existente = Horario.query.filter_by(nombre=nombre).first()
        if horario_existente:
            flash(f'Error: Ya existe un horario con el nombre "{nombre}".', 'danger')
            return redirect(url_for('main.gestion_horarios'))

        try:
            nuevo_horario = Horario(nombre=nombre)
            db.session.add(nuevo_horario)
            db.session.commit()
            flash(f'Horario "{nombre}" creado con éxito.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el horario: {e}', 'danger')

    return redirect(url_for('main.gestion_horarios'))


@main_bp.route('/horario/eliminar/<int:horario_id>', methods=['POST'])
@login_required
def horario_eliminar(horario_id):
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    horario = Horario.query.get_or_404(horario_id)

    empleados_asociados = Empleado.query.filter_by(id_horario=horario.id).count()
    if empleados_asociados > 0:
        flash(f'Error: El horario "{horario.nombre}" no se puede eliminar porque tiene {empleados_asociados} empleados asociados.', 'danger')
        return redirect(url_for('main.gestion_horarios'))

    try:
        db.session.delete(horario)
        db.session.commit()
        flash(f'Horario "{horario.nombre}" eliminado con éxito (y sus franjas).', 'success')
    except UnmappedInstanceError:
        flash('Error: El horario que intentas eliminar ya no existe.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el horario: {e}', 'danger')

    return redirect(url_for('main.gestion_horarios'))


@main_bp.route('/franja/nuevo/<int:horario_id>', methods=['POST'])
@login_required
def franja_nuevo(horario_id):
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    horario = Horario.query.get_or_404(horario_id)

    franja_id = request.form.get('franja_id', type=int)

    dia_semana = request.form.get('dia_semana', type=int)
    hora_inicio = request.form.get('hora_inicio')
    hora_fin = request.form.get('hora_fin')

    # Validación: Las franjas no se pueden solapar
    error_solapamiento = check_solapamiento(horario_id, dia_semana, hora_inicio, hora_fin, franja_id=franja_id)
    if error_solapamiento:
        flash(f'Error de Franja: {error_solapamiento}', 'danger')
        return redirect(url_for('main.gestion_horarios', _anchor=f'horario-{horario_id}'))

    try:
        t_inicio = datetime.strptime(hora_inicio, '%H:%M').time()
        t_fin = datetime.strptime(hora_fin, '%H:%M').time()

        if franja_id:
            # Lógica de MODIFICACIÓN
            franja = FranjaHoraria.query.get_or_404(franja_id)
            franja.dia_semana = dia_semana
            franja.hora_inicio = t_inicio
            franja.hora_fin = t_fin
            db.session.commit()
            flash(f'Franja horaria modificada con éxito.', 'success')

        else:
            # Lógica de CREACIÓN
            nueva_franja = FranjaHoraria(
                id_horario=horario_id,
                dia_semana=dia_semana,
                hora_inicio=t_inicio,
                hora_fin=t_fin
            )
            db.session.add(nueva_franja)
            db.session.commit()
            flash(f'Franja horaria para el Horario "{horario.nombre}" añadida con éxito.', 'success')

    except IntegrityError:
        db.session.rollback()
        flash('Error: Ya existe una franja idéntica para ese día y hora.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar la franja: {e}', 'danger')

    return redirect(url_for('main.gestion_horarios', _anchor=f'horario-{horario_id}'))


@main_bp.route('/franja/eliminar/<int:franja_id>', methods=['POST'])
@login_required
def franja_eliminar(franja_id):
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    franja = FranjaHoraria.query.get_or_404(franja_id)
    horario_id = franja.id_horario

    try:
        db.session.delete(franja)
        db.session.commit()
        flash('Franja horaria eliminada con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la franja: {e}', 'danger')

    return redirect(url_for('main.gestion_horarios', _anchor=f'horario-{horario_id}'))

@main_bp.route('/ver_registros')
@login_required
def ver_registros():
    admin_check = requires_admin_or_superadmin()
    if admin_check:
        return admin_check

    if current_user.rol_obj.nombre == 'Superadministrador':
        registros = Registro.query.order_by(Registro.hora_entrada.desc()).all()
    else:
        registros = Registro.query.join(Empleado).filter(
            Empleado.id_empresa == current_user.id_empresa
        ).order_by(Registro.hora_entrada.desc()).all()

    return render_template('ver_registros.html', registros=registros)