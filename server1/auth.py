#!/usr/bin/env python
# -*- Mode: Python; tab-width: 4; indent-tabs-mode: nil; coding: utf-8; -*-
# vim:set ft=python ts=4 sw=4 sts=4 autoindent:

'''
Mecanismos de autenticación y autorización.

Autor:     Pontus Stenetorp    <pontus is s u-tokyo ac jp>
            Illes Solt          <solt tmit bme hu>
Versión:   2011-04-21
'''

from hashlib import sha512  # Importa el algoritmo SHA-512 para cifrado de contraseñas.
from os.path import dirname, join as path_join, isdir  # Funciones para manejo de rutas de archivos y directorios.

try:
    from os.path import relpath  # Importa relpath para obtener la ruta relativa de un archivo.
except ImportError:
    # relpath es nuevo en Python 2.6; usamos nuestra propia implementación si no está disponible.
    from common import relpath  # Importamos nuestra implementación de relpath.
from common import ProtocolError  # Importa la clase base de errores de protocolo.
from config import USER_PASSWORD, DATA_DIR  # Importa los usuarios y contraseñas configurados y el directorio de datos.
from message import Messager  # Importa la clase que maneja el envío de mensajes a la interfaz.
from session import get_session, invalidate_session  # Importa funciones para manejar las sesiones de usuario.
from projectconfig import ProjectConfiguration  # Importa la clase para la configuración de proyectos.

# Excepción que se lanza cuando falta la autoridad para realizar una operación.
class NotAuthorisedError(ProtocolError):
    def __init__(self, attempted_action):
        self.attempted_action = attempted_action  # Acción que se intentó realizar sin autorización.

    def __str__(self):
        return 'Se requiere iniciar sesión para realizar "%s"' % self.attempted_action  # Mensaje de error.

    def json(self, json_dic):
        json_dic['exception'] = 'notAuthorised'  # Añade información del error en formato JSON.
        return json_dic

# Excepción para denegar acceso a archivos o datos.
class AccessDeniedError(ProtocolError):
    def __init__(self):
        pass

    def __str__(self):
        return 'Acceso Denegado'  # Mensaje de error cuando el acceso es denegado.

    def json(self, json_dic):
        json_dic['exception'] = 'accessDenied'  # Añade información del error en formato JSON.
        # TODO: El cliente debería ser responsable aquí.
        Messager.error('Acceso Denegado')  # Envía un mensaje de error al cliente.
        return json_dic

# Excepción para cuando la autenticación es inválida (usuario o contraseña incorrectos).
class InvalidAuthError(ProtocolError):
    def __init__(self):
        pass

    def __str__(self):
        return 'Usuario y/o contraseña incorrectos'  # Mensaje de error cuando la autenticación falla.

    def json(self, json_dic):
        json_dic['exception'] = 'invalidAuth'  # Añade información del error en formato JSON.
        return json_dic

# Verifica si el usuario está autenticado.
def _is_authenticated(user, password):
    # TODO: Reemplazar con un backend de base de datos.
    return (user in USER_PASSWORD and  # Verifica si el usuario existe.
            password == USER_PASSWORD[user])  # Verifica si la contraseña es correcta.
            #password == _password_hash(USER_PASSWORD[user]))  # (Código comentado para usar contraseñas cifradas).

# Genera el hash de la contraseña utilizando SHA-512.
def _password_hash(password):
    return sha512(password).hexdigest()  # Devuelve el hash de la contraseña.

# Función para iniciar sesión.
def login(user, password):
    if not _is_authenticated(user, password):  # Verifica si las credenciales son correctas.
        raise InvalidAuthError  # Lanza un error si la autenticación falla.

    get_session()['user'] = user  # Guarda el usuario en la sesión.
    Messager.info('¡Hola!')  # Envía un mensaje de saludo al cliente.
    return {}

# Función para cerrar sesión.
def logout():
    try:
        del get_session()['user']  # Elimina el usuario de la sesión.
    except KeyError:
        # Si ya está eliminado, no hace nada.
        pass
    # TODO: ¿Realmente enviar este mensaje?
    Messager.info('¡Adiós!')  # Envía un mensaje de despedida al cliente.
    return {}

# Función para obtener el usuario actual (quién está autenticado).
def whoami():
    json_dic = {}
    try:
        json_dic['user'] = get_session().get('user')  # Intenta obtener el usuario de la sesión.
    except KeyError:
        # TODO: ¿Realmente enviar este mensaje?
        Messager.error('¡No has iniciado sesión!', duration=3)  # Envía un mensaje de error si no hay sesión.
    return json_dic

# Función que verifica si se permite leer un archivo o directorio.
def allowed_to_read(real_path):
    data_path = path_join('/', relpath(real_path, DATA_DIR))  # Obtiene la ruta relativa dentro del directorio de datos.
    # Añade una barra al final si es un directorio, requerido para cumplir con robots.txt.
    if isdir(real_path):
        data_path = '%s/' % (data_path)
        
    real_dir = dirname(real_path)  # Obtiene el directorio que contiene el archivo.
    robotparser = ProjectConfiguration(real_dir).get_access_control()  # Obtiene la configuración de acceso del proyecto.
    if robotparser is None:
        return True  # Permitir acceso por defecto si no hay configuración.

    try:
        user = get_session().get('user')  # Intenta obtener el usuario actual de la sesión.
    except KeyError:
        user = None

    if user is None:
        user = 'guest'  # Si no hay usuario, se considera un usuario invitado (guest).

    # display_message('Path: %s, dir: %s, user: %s, ' % (data_path, real_dir, user), type='error', duration=-1)

    return robotparser.can_fetch(user, data_path)  # Verifica si el usuario puede acceder al archivo o directorio.

# TODO: Pruebas unitarias.
