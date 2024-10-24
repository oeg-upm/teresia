#!/usr/bin/env python

from __future__ import with_statement  # Compatibilidad para usar la declaración 'with' en versiones antiguas de Python.

'''
Proporciona un mecanismo elegante de bloqueo de archivos en Python:

>>>    with('file.lock'):
...        pass

Inspirado por: http://code.activestate.com/recipes/576572/

Es específico para *NIX debido al uso del comando 'ps' (se agradecen sugerencias sobre cómo evitar esto).

Incluye tiempo de espera (timeout) y verificación de PID para evitar archivos de bloqueo obsoletos.
También incluye algunas pruebas unitarias.

Autor:     Pontus Stenetorp    <pontus stenetorp se>
Versión:   2009-12-26
'''

'''
Copyright (c) 2009, 2011, Pontus Stenetorp <pontus stenetorp se>

Se otorga permiso para usar, copiar, modificar y/o distribuir este software
para cualquier propósito con o sin tarifa, siempre que se incluya el aviso
de copyright anterior y este permiso en todas las copias.

EL SOFTWARE SE PROPORCIONA "TAL CUAL" Y EL AUTOR RENUNCIA A TODAS LAS
GARANTÍAS CON RESPECTO A ESTE SOFTWARE, INCLUYENDO TODAS LAS GARANTÍAS
IMPLÍCITAS DE COMERCIABILIDAD Y ADECUACIÓN PARA UN PROPÓSITO PARTICULAR.
EN NINGÚN CASO EL AUTOR SERÁ RESPONSABLE DE DAÑOS ESPECIALES, DIRECTOS,
INDIRECTOS O CONSECUENCIALES O CUALQUIER OTRO DAÑO DERIVADO DEL USO
O RENDIMIENTO DEL SOFTWARE.
'''

'''
Copyright (C) 2008 by Aaron Gallagher

Se otorga permiso, de forma gratuita, a cualquier persona que obtenga
una copia de este software y los archivos de documentación asociados
(el "Software"), para usar el Software sin restricciones, incluyendo
los derechos de usar, copiar, modificar, fusionar, publicar, distribuir,
sub-licenciar y/o vender copias del Software.

EL SOFTWARE SE PROPORCIONA "TAL CUAL", SIN GARANTÍA DE NINGÚN TIPO,
EXPRESA O IMPLÍCITA.
'''

from contextlib import contextmanager  # Importa el manejador de contexto.
from errno import EEXIST  # Importa el error de archivo ya existente.
from os import (remove, read, fsync, open, close, write, getpid,
        O_CREAT, O_EXCL, O_RDWR, O_RDONLY)  # Funciones de manejo de archivos y procesos.
from subprocess import Popen, PIPE  # Permite ejecutar procesos externos.
from time import time, sleep  # Para controlar el tiempo y las pausas.
from sys import stderr  # Para imprimir errores en la salida de error estándar.

### Constantes
# No permite ignorar un archivo de bloqueo si el PID no está activo.
PID_DISALLOW = 1
# Ignora un archivo de bloqueo si el PID no está activo, pero muestra una advertencia.
PID_WARN = 2
# Ignora un archivo de bloqueo si el PID no está activo.
PID_ALLOW = 3
###

# Clase de error para manejar el tiempo de espera de bloqueo de archivo.
class FileLockTimeoutError(Exception):
    '''
    Se lanza si no se puede adquirir el bloqueo del archivo antes de que se alcance el tiempo de espera.
    '''
    def __init__(self, timeout):
        self.timeout = timeout  # Tiempo de espera que provocó el error.

    def __str__(self):
        return 'Tiempo de espera agotado al intentar adquirir el bloqueo, se esperó (%d)s' % (
                self.timeout)


def _pid_exists(pid):
    '''
    Devuelve True si el PID dado es un identificador de proceso que existe actualmente.

    Argumentos:
    pid - Identificador de proceso (PID) para verificar si existe en el sistema.
    '''
    # No es elegante, pero parece ser la única forma de hacerlo.
    ps = Popen("ps %d | awk '{{print $1}}'" % (pid, ),  # Ejecuta el comando 'ps' para verificar si el PID existe.
            shell=True, stdout=PIPE)
    ps.wait()  # Espera a que el comando finalice.
    return str(pid) in ps.stdout.read().split('\n')  # Verifica si el PID aparece en la salida del comando 'ps'.

# Decorador de contexto para manejar el bloqueo de archivos.
@contextmanager
def file_lock(path, wait=0.1, timeout=1,
        pid_policy=PID_DISALLOW, err_output=stderr):
    '''
    Usa la ruta dada para un archivo de bloqueo que contiene el PID del proceso.
    Si se solicita otro bloqueo para el mismo archivo, se pueden establecer políticas para determinar cómo manejarlo.

    Argumentos:
    path - Ruta donde colocar el archivo de bloqueo o donde ya está colocado.
    
    Argumentos opcionales:
    wait - Tiempo de espera entre intentos de bloqueo del archivo.
    timeout - Duración para intentar bloquear el archivo hasta que se lance una excepción de tiempo de espera.
    pid_policy - Una política de PID como las encontradas en este módulo, válidas son PID_DISALLOW, PID_WARN y PID_ALLOW.
    err_output - Dónde imprimir los mensajes de advertencia, utilizado con fines de prueba.
    '''
    start_time = time()  # Obtiene el tiempo inicial.
    while True:
        if time() - start_time > timeout:  # Si el tiempo transcurrido excede el tiempo de espera.
            raise FileLockTimeoutError(timeout)  # Lanza un error de tiempo de espera.
        try:
            fd = open(path, O_CREAT | O_EXCL | O_RDWR)  # Intenta crear el archivo de bloqueo.
            write(fd, str(getpid()))  # Escribe el PID del proceso en el archivo de bloqueo.
            fsync(fd)  # Asegura que los datos se escriban en el disco.
            break  # Sale del ciclo si se pudo crear el archivo de bloqueo.
        except OSError as e:
            if e.errno == EEXIST:  # Si el archivo de bloqueo ya existe.
                if pid_policy == PID_DISALLOW:  # Si la política es no permitir.
                    pass  # No hacer nada.
                elif pid_policy in [PID_WARN, PID_ALLOW]:  # Si la política es advertir o permitir.
                    fd = open(path, O_RDONLY)  # Abre el archivo de bloqueo en modo de solo lectura.
                    pid = int(read(fd, 255))  # Lee el PID del archivo de bloqueo.
                    close(fd)  # Cierra el archivo.
                    if not _pid_exists(pid):  # Si el proceso con ese PID no existe.
                        if pid_policy == PID_WARN:  # Si la política es advertir.
                            print >> err_output, (
                                    "Archivo de bloqueo obsoleto '%s', eliminando" % (
                                        path))  # Muestra una advertencia.
                        remove(path)  # Elimina el archivo de bloqueo obsoleto.
                        continue  # Vuelve a intentar crear el bloqueo.
                else:
                    assert False, 'Argumento de política de PID inválido'  # Si la política es inválida.
            else:
                raise  # Lanza cualquier otro error de OSError.
        sleep(wait)  # Espera antes de volver a intentar.
    try:
        yield fd  # Devuelve el descriptor de archivo del archivo de bloqueo.
    finally:
        close(fd)  # Cierra el archivo de bloqueo.
        remove(path)  # Elimina el archivo de bloqueo.

# Bloque de pruebas unitarias.
if __name__ == '__main__':
    from unittest import TestCase  # Importa las pruebas unitarias.
    import unittest

    from multiprocessing import Process  # Para crear procesos paralelos.
    from os import rmdir  # Para eliminar directorios.
    from os.path import join, isfile  # Para unir rutas y verificar la existencia de archivos.
    from tempfile import mkdtemp  # Para crear un directorio temporal.

    try:
        from cStringIO import StringIO  # Para manejar cadenas como archivos (en Python 2.x).
    except ImportError:
        from StringIO import StringIO  # Para Python 3.x.

    # Clase de prueba para el bloqueo de archivos.
    class TestFileLock(TestCase):
        def setUp(self):
            self._temp_dir = mkdtemp()  # Crea un directorio temporal.
            self._lock_file_path = join(self._temp_dir, 'lock.file')  # Define la ruta del archivo de bloqueo.

        def tearDown(self):
            try:
                remove(self._lock_file_path)  # Intenta eliminar el archivo de bloqueo.
            except OSError:
                pass  # Si no existe, no hacer nada.
            rmdir(self._temp_dir)  # Elimina el directorio temporal.

        def test_with(self):
            '''
            Prueba la funcionalidad 'with'.
            '''
            with file_lock(self._lock_file_path):
                sleep(1)  # Simula una operación que mantiene el bloqueo.
            sleep(0.1)  # Asegura que el archivo se haya eliminado.
            self.assertFalse(isfile(self._lock_file_path))  # Verifica que el archivo de bloqueo haya sido eliminado.

        def test_exception(self):
            '''
            Prueba si el archivo de bloqueo no permanece si ocurre una excepción.
            '''
            try:
                with file_lock(self._lock_file_path):
                    raise Exception('Interrumpiendo')  # Genera una excepción dentro del bloque 'with'.
            except Exception:
                pass

            self.assertFalse(isfile(self._lock_file_path))  # Verifica que el archivo de bloqueo haya sido eliminado.

        def test_timeout(self):
            '''
            Prueba si se alcanza un tiempo de espera.
            '''
            # Usa un tiempo de espera imposible.
            try:
                with file_lock(self._lock_file_path, timeout=-1):
                    pass
                self.assertTrue(False, 'No debería llegar a este punto')  # Esta línea no debería ejecutarse.
            except FileLockTimeoutError:
                pass  # El tiempo de espera debería provocar un error.

        def test_lock(self):
            '''
            Prueba si un bloqueo está realmente en su lugar.
            '''
            def process_task(path):
                with file_lock(path):
                    sleep(1)  # Simula una operación que mantiene el bloqueo.
                return 0

            process = Process(target=process_task, args=[self._lock_file_path])
            process.start()  # Inicia el proceso paralelo.
            sleep(0.5)  # Asegura que el archivo se haya creado en disco.
            self.assertTrue(isfile(self._lock_file_path))  # Verifica que el archivo de bloqueo exista.
            sleep(1)

        def _fake_crash_other_process(self):
            '''
            Método auxiliar para emular un cierre forzado que deja un archivo de bloqueo intacto.
            '''
            def process_task(path):
                fd = open(path, O_CREAT | O_RDWR)
                try:
                    write(fd, str(getpid()))  # Escribe el PID en el archivo de bloqueo.
                finally:
                    close(fd)  # Cierra el archivo.
                return 0

            process = Process(target=process_task, args=[self._lock_file_path])
            process.start()  # Inicia el proceso.
            while process.is_alive():
                sleep(0.1)  # Espera a que el proceso finalice.
            return process.pid  # Devuelve el PID del proceso.

        def test_crash(self):
            '''
            Prueba que el mecanismo de bloqueo después de un cierre forzado funcione.
            '''
            pid = self._fake_crash_other_process()  # Simula un cierre forzado.
            self.assertTrue(isfile(self._lock_file_path))  # Verifica que el archivo de bloqueo exista.
            self.assertTrue(pid == int(
                read(open(self._lock_file_path, O_RDONLY), 255)))  # Verifica que el PID en el archivo coincida.

        ###
        def test_pid_disallow(self):
            '''
            Prueba si los archivos de bloqueo obsoletos se respetan si se establece la política de disallow.
            '''
            self._fake_crash_other_process()  # Simula un cierre forzado.
            try:
                with file_lock(self._lock_file_path, pid_policy=PID_DISALLOW):
                    self.assertTrue(False, 'No debería llegar a este punto')  # No debería alcanzar esta línea.
            except FileLockTimeoutError:
                pass  # Debería lanzar un error de tiempo de espera.

        def test_pid_warn(self):
            '''
            Prueba si un archivo de bloqueo obsoleto provoca una advertencia en stderr y luego se ignora con la política de warn.
            '''
            self._fake_crash_other_process()  # Simula un cierre forzado.
            err_output = StringIO()  # Crea un objeto para capturar la salida de error.
            try:
                with file_lock(self._lock_file_path, pid_policy=PID_WARN,
                        err_output=err_output):
                    pass
            except FileLockTimeoutError:
                self.assertTrue(False, 'No debería llegar a este punto')  # No debería alcanzar esta línea.
            err_output.seek(0)  # Vuelve al inicio de la captura de salida.
            self.assertTrue(err_output.read(), 'No hubo salida, aunque la política de advertencia estaba activada')  # Verifica que se haya emitido una advertencia.

        def test_pid_allow(self):
            '''
            Prueba si un archivo de bloqueo obsoleto se ignora sin notificar con la política de allow.
            '''
            self._fake_crash_other_process()  # Simula un cierre forzado.
            err_output = StringIO()  # Crea un objeto para capturar la salida de error.
            try:
                with file_lock(self._lock_file_path, pid_policy=PID_ALLOW,
                        err_output=err_output):
                    pass
            except FileLockTimeoutError:
                self.assertTrue(False, 'No debería llegar a este punto')  # No debería alcanzar esta línea.
            err_output.seek(0)  # Vuelve al inicio de la captura de salida.
            self.assertFalse(err_output.read(), 'Hubo salida, aunque la política de allow estaba activada')  # Verifica que no haya advertencias.

    unittest.main()  # Ejecuta las pruebas unitarias.
