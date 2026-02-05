from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from extensions import db, bcrypt
from models import Empleado, Registro, Empresa
from datetime import datetime
import math

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    nif = data.get('nif')
    password = data.get('password')

    user = Empleado.query.filter_by(nif=nif).first()

    if user and user.check_password(password):
        access_token = create_access_token(identity=str(user.id))
        return jsonify(access_token=access_token), 200
    
    return jsonify({"msg": "NIF o contraseña incorrectos"}), 401

def calcular_distancia(lat1, lon1, lat2, lon2):
    if None in [lat1, lon1, lat2, lon2]: return 999999 # Distancia infinita si faltan datos
    R = 6371000 # Radio de la Tierra en metros
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

@api_bp.route('/presencia/fichar', methods=['POST'])
@jwt_required()
def fichar():
    user_id = get_jwt_identity()
    user = Empleado.query.get(user_id)
    empresa = user.empresa_obj
    data = request.get_json()

    lat_movil = data.get('lat')
    lng_movil = data.get('lng')
    tipo = data.get('tipo')

    distancia = calcular_distancia(lat_movil, lng_movil, empresa.lat, empresa.lng)
    
    if distancia > empresa.radio:
        return jsonify({
            "msg": "Estás fuera del radio permitido", 
            "distancia_actual": round(distancia, 2),
            "radio_maximo": empresa.radio
        }), 403

    if tipo == 'entrada':
        if Registro.query.filter_by(id_trabajador=user_id, hora_salida=None).first():
            return jsonify({"msg": "Ya tienes una entrada registrada sin cerrar"}), 400
        
        nuevo_fichaje = Registro(hora_entrada=datetime.now(), id_trabajador=user_id)
        db.session.add(nuevo_fichaje)
    
    elif tipo == 'salida':
        registro = Registro.query.filter_by(id_trabajador=user_id, hora_salida=None).first()
        if not registro:
            return jsonify({"msg": "No hay ninguna entrada abierta para cerrar"}), 400
        
        registro.hora_salida = datetime.now()
    
    db.session.commit()
    return jsonify({"msg": f"Registro de {tipo} realizado con éxito"}), 200