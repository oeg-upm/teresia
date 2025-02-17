#!/usr/bin/env python

# Servidor mínimo independiente de brat basado en CGIHTTPRequestHandler.

# Se ejecuta como apache, por ejemplo, como:
#
#     APACHE_USER=./apache-user.sh
#     sudo -u $APACHE_USER python standalone.py

import sys
import os

from posixpath import normpath  # Función para normalizar rutas POSIX (Unix).
from urllib import unquote  # Decodifica URLs, como %20 en espacios.

from cgi import FieldStorage  # Para manejar formularios y datos CGI.
from BaseHTTPServer import HTTPServer  # Servidor HTTP básico.
from SimpleHTTPServer import SimpleHTTPRequestHandler  # Maneja solicitudes HTTP simples.
from SocketServer import ForkingMixIn  # Permite manejar múltiples solicitudes con bifurcación (forking).
from CGIHTTPServer import CGIHTTPRequestHandler  # Maneja solicitudes CGI en el servidor HTTP.
import socket  # Permite la comunicación de red.

# Importaciones de brat.
sys.path.append(os.path.join(os.path.dirname(__file__), 'server/src'))
from server import serve  # Función principal para manejar las solicitudes del servidor brat.

# Preimporta todo lo necesario (comentario dice que se debe limpiar en el futuro).
import annlog  # Manejo de logs de anotación.
import annotation  # Manejo de anotaciones.
import annotator  # Gestión de anotadores.
import auth  # Autenticación de usuarios.
import common  # Funciones comunes utilizadas en varios módulos.
import delete  # Eliminación de anotaciones o documentos.
import dispatch  # Gestión de solicitudes a diferentes módulos.
import docimport  # Importación de documentos.
import document  # Manejo de documentos.
import download  # Descarga de archivos.
import filelock  # Bloqueo de archivos para evitar accesos concurrentes.
import gtbtokenize  # Tokenización para formatos específicos.
import jsonwrap  # Manejo de JSON.
import message  # Manejo de mensajes.
import normdb  # Base de datos de normalización de texto.
import norm  # Normalización de anotaciones.
import predict  # Predicción de anotaciones.
import projectconfig  # Configuración de proyectos en brat.
import realmessage  # Mensajes en tiempo real.
import sdistance  # Cálculo de distancias semánticas.
import search  # Búsqueda de anotaciones/documentos.
import server  # Servidor principal de brat.
import session  # Manejo de sesiones de usuario.
import simstringdb  # Base de datos SimString para búsquedas.
import sosmessage  # Mensajes de ayuda en caso de error.
import ssplit  # Segmentación de oraciones.
import sspostproc  # Post-procesamiento de segmentación de oraciones.
import stats  # Estadísticas de uso.
import svg  # Generación de gráficos SVG.
import tag  # Etiquetado de anotaciones.
import tokenise  # Tokenización de texto.
import undo  # Funciones para deshacer acciones.
import verify_annotations  # Verificación de anotaciones.

_VERBOSE_HANDLER = False  # Controla si se deben imprimir los logs de manejo de solicitudes.
_DEFAULT_SERVER_ADDR = ''  # Dirección por defecto del servidor.
_DEFAULT_SERVER_PORT = 8082  # Puerto por defecto del servidor.

# Permisos definidos para el acceso a rutas específicas del servidor.
_PERMISSIONS = """
Allow: /ajax.cgi
Disallow: *.py
Disallow: *.cgi
Disallow: /.htaccess
Disallow: *.py~  # no se permiten archivos de respaldo de emacs
Disallow: *.cgi~
Disallow: /.htaccess~
Allow: /
"""

# Clase para manejar errores de análisis de permisos.
class PermissionParseError(Exception):
    def __init__(self, linenum, line, message=None):
        self.linenum = linenum  # Número de línea donde ocurrió el error.
        self.line = line  # Contenido de la línea con el error.
        self.message = ' (%s)' % message if message is not None else ''
    
    def __str__(self):
        return 'line %d%s: %s' % (self.linenum, self.message, self.line)

# Clase para manejar patrones de rutas permitidas.
class PathPattern(object):
    def __init__(self, path):
        self.path = path  # Ruta permitida.
        self.plen = len(path)  # Longitud de la ruta.

    def match(self, s):
        # Verifica si la ruta solicitada coincide con la permitida.
        return s[:self.plen] == self.path and (self.path[-1] == '/' or
                                               s[self.plen:] == '' or 
                                               s[self.plen] == '/')

# Clase para manejar extensiones de archivos permitidos.
class ExtensionPattern(object):
    def __init__(self, ext):
        self.ext = ext  # Extensión permitida (e.g., ".cgi").

    def match(self, s):
        # Verifica si la extensión del archivo coincide con la permitida.
        return os.path.splitext(s)[1] == self.ext

# Clase para manejar los permisos de acceso a rutas.
class PathPermissions(object):
    """Implementa la verificación de permisos de ruta con una sintaxis similar a robots.txt."""

    def __init__(self, default_allow=False):
        self._entries = []  # Lista de patrones permitidos o denegados.
        self.default_allow = default_allow  # Indica si por defecto se permite el acceso.

    def allow(self, path):
        # La primera coincidencia de patrón determina si se permite el acceso.
        for pattern, allow in self._entries:
            if pattern.match(path):
                return allow
        return self.default_allow
    
    def parse(self, lines):
        # Analiza las líneas de permisos para determinar qué rutas están permitidas o denegadas.

        for ln, l in enumerate(lines):            
            i = l.find('#')  # Ignora comentarios (líneas que empiezan con #).
            if i != -1:
                l = l[:i]
            l = l.strip()

            if not l:
                continue

            i = l.find(':')
            if i == -1:
                raise PermissionParseError(ln, lines[ln], 'missing colon')

            directive = l[:i].strip().lower()
            pattern = l[i+1:].strip()

            if directive == 'allow':
                allow = True
            elif directive == 'disallow':
                allow = False
            else:
                raise PermissionParseError(ln, lines[ln], 'unrecognized directive')
            
            if pattern.startswith('/'):
                patt = PathPattern(pattern)
            elif pattern.startswith('*.'):
                patt = ExtensionPattern(pattern[1:])
            else:
                raise PermissionParseError(ln, lines[ln], 'unrecognized pattern')

            self._entries.append((patt, allow))

        return self

# Clase que maneja las solicitudes HTTP específicas de brat.
class BratHTTPRequestHandler(CGIHTTPRequestHandler):
    """Manejador mínimo para el servidor brat."""

    permissions = PathPermissions().parse(_PERMISSIONS.split('\n'))  # Analiza los permisos.

    def log_request(self, code='-', size='-'):
        if _VERBOSE_HANDLER:
            CGIHTTPRequestHandler.log_request(self, code, size)
        else:
            # Ignora los logs si no están activados.
            pass

    def is_brat(self):
        # Limpia y verifica si la ruta solicitada es parte de brat.
        path = self.path
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]

        if path == '/ajax.cgi':
            return True
        else:
            return False    

    def run_brat_direct(self):
        """Ejecuta directamente el servidor brat."""

        remote_addr = self.client_address[0]  # Dirección IP del cliente.
        remote_host = self.address_string()  # Nombre del host del cliente.
        cookie_data = ', '.join(filter(None, self.headers.getheaders('cookie')))  # Cookies enviadas por el cliente.

        query_string = ''
        i = self.path.find('?')
        if i != -1:
            query_string = self.path[i+1:]
            
        saved = sys.stdin, sys.stdout, sys.stderr
        sys.stdin, sys.stdout = self.rfile, self.wfile  # Redirige las entradas/salidas al cliente.

        # Prepara el entorno para que FieldStorage pueda leer los parámetros.
        env = {}
        env['REQUEST_METHOD'] = self.command  # Método de la solicitud (GET, POST, etc.).
        content_length = self.headers.getheader('content-length')
        if content_length:
            env['CONTENT_LENGTH'] = content_length
        if query_string:
            env['QUERY_STRING'] = query_string
        os.environ.update(env)
        params = FieldStorage()  # Lee los parámetros de la solicitud.

        # Llama al servidor principal de brat.
        cookie_hdrs, response_data = serve(params, remote_addr, remote_host, cookie_data)

        sys.stdin, sys.stdout, sys.stderr = saved

        # Empaqueta y envía la respuesta al cliente.
        if cookie_hdrs is not None:
            response_hdrs = [hdr for hdr in cookie_hdrs]
        else:
            response_hdrs = []
        response_hdrs.extend(response_data[0])

        self.send_response(200)  # Código HTTP 200 (éxito).
        self.wfile.write('\n'.join('%s: %s' % (k, v) for k, v in response_hdrs))
        self.wfile.write('\n')
        self.wfile.write('\n')
        # Soporte para datos binarios y texto Unicode (para SVGs y JSON).
        if isinstance(response_data[1], unicode):
            self.wfile.write(response_data[1].encode('utf-8'))
        else:
            self.wfile.write(response_data[1])
        return 0

    def run_brat_exec(self):
        """Ejecuta el servidor brat utilizando execfile('ajax.cgi')."""

        scriptfile = self.translate_path('/ajax.cgi')  # Traduce la ruta a la ruta del script.

        env = {}
        env['REQUEST_METHOD'] = self.command
        env['REMOTE_HOST'] = self.address_string()
        env['REMOTE_ADDR'] = self.client_address[0]
        env['CONTENT_LENGTH'] = self.headers.getheader('content-length')
        env['HTTP_COOKIE'] = ', '.join(filter(None, self.headers.getheaders('cookie')))
        os.environ.update(env)

        self.send_response(200)

        try:
            saved = sys.stdin, sys.stdout, sys.stderr
            sys.stdin, sys.stdout = self.rfile, self.wfile
            sys.argv = [scriptfile]
            try:
                execfile(scriptfile, {'__name__': '__main__', '__file__': __file__ })
            finally:
                sys.stdin, sys.stdout, sys.stderr = saved
        except SystemExit, sts:
            print >> sys.stderr, 'exit status', sts
        else:
            print >> sys.stderr, 'exit OK'

    def allow_path(self):
        """Verifica si se permite el acceso a self.path."""

        path = self.path
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = unquote(path)  # Decodifica la URL.
        path = normpath(path)  # Normaliza la ruta.
        parts = path.split('/')
        parts = filter(None, parts)
        if '..' in parts:  # No permite acceder a rutas fuera de los directorios permitidos.
            return False
        path = '/'+'/'.join(parts)

        return self.permissions.allow(path)  # Verifica los permisos.

    def list_directory(self, path):
        """Sobrescribe la función de listar directorios."""
        self.send_error(403)  # No permite listar directorios (protegido).

    def do_POST(self):
        """Sirve una solicitud POST. Solo está implementado para brat."""

        if self.is_brat():
            self.run_brat_direct()  # Ejecuta brat si es una solicitud válida.
        else:
            self.send_error(501, "Solo se puede hacer POST a brat.")

    def do_GET(self):
        """Sirve una solicitud GET."""
        if not self.allow_path():
            self.send_error(403)  # Deniega el acceso si no está permitido.
        elif self.is_brat():
            self.run_brat_direct()  # Ejecuta brat si es una solicitud válida.
        else:
            CGIHTTPRequestHandler.do_GET(self)

    def do_HEAD(self):
        """Sirve una solicitud HEAD."""
        if not self.allow_path():
            self.send_error(403)  # Deniega el acceso si no está permitido.
        else:
            CGIHTTPRequestHandler.do_HEAD(self)
       
# Clase que define el servidor brat con múltiples procesos.
class BratServer(ForkingMixIn, HTTPServer):
    def __init__(self, server_address):
        HTTPServer.__init__(self, server_address, BratHTTPRequestHandler)

def main(argv):
    # Muestra una advertencia si se ejecuta como root/administrador.
    try:
        if os.getuid() == 0:
            print >> sys.stderr, """
! ADVERTENCIA: ejecutándose como root. El servidor independiente de brat es experimental
y puede ser un riesgo de seguridad. Se recomienda ejecutarlo como un usuario no root
con permisos de escritura en los directorios work/ y data/ de brat.
"""
    except AttributeError:
        # Si no es un sistema UNIX.
        print >> sys.stderr, """
Advertencia: no se pudo determinar el usuario. El servidor independiente de brat
es experimental y no debe ejecutarse como administrador.
"""

    if len(argv) > 1:
        try:
            port = int(argv[1])  # Toma el puerto de los argumentos.
        except ValueError:
            print >> sys.stderr, "Error al analizar", argv[1], "como número de puerto."
            return 1
    else:
        port = _DEFAULT_SERVER_PORT  # Usa el puerto por defecto.

    try:
        server = BratServer((_DEFAULT_SERVER_ADDR, port))  # Inicia el servidor.
        print >> sys.stderr, "Servidor brat en http://127.0.0.1:%d" % port
        server.serve_forever()  # El servidor empieza a atender solicitudes.
    except KeyboardInterrupt:
        # Salida normal si se interrumpe con Ctrl+C.
        pass
    except socket.error, why:
        print >> sys.stderr, "Error al enlazar al puerto", port, ":", why[1]
    except Exception, e:
        print >> sys.stderr, "Error en el servidor", e
        raise
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))  # Inicia la ejecución del servidor brat.
