import os
import gpxpy
import argparse
import geopy.distance
from geopy.geocoders import Nominatim
import unidecode
import time
import shutil
from datetime import datetime

def obtener_datos_gpx(archivo_gpx):
    # Abre y parsea el archivo GPX
    with open(archivo_gpx, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    
    # Verifica que haya tracks, segmentos y puntos en el archivo GPX
    if not gpx.tracks or not gpx.tracks[0].segments or not gpx.tracks[0].segments[0].points:
        raise ValueError("El archivo GPX no contiene puntos válidos")

    # Extrae el primer punto del primer segmento del primer track
    punto_origen = gpx.tracks[0].segments[0].points[0]

    # Intenta obtener la marca de tiempo del punto, si no existe, intenta obtenerla de metadata
    if punto_origen.time:
        fecha_hora_origen = punto_origen.time.strftime('%Y-%m-%d_%H-%M')
    else:
        # Busca la marca de tiempo en la metadata de cada track
        for track in gpx.tracks:
            if track.get_time_bounds().start_time:
                fecha_hora_origen = track.get_time_bounds().start_time.strftime('%Y-%m-%d_%H-%M')
                break
        else:
            # Si no se encuentra la marca de tiempo en ninguna metadata, asigna 'SinFechaHora'
            fecha_hora_origen = 'SinFechaHora'
    
    origen = {
        'Fecha-Hora': fecha_hora_origen,
        'Latitud': punto_origen.latitude,
        'Longitud': punto_origen.longitude,
        'Elevacion': punto_origen.elevation,
        'Creador': gpx.creator  # Agrega el nombre del creador extraído del archivo GPX
    }

    # Extrae el último punto del último segmento del primer track
    punto_destino = gpx.tracks[0].segments[-1].points[-1]
    destino = {
        'Latitud': punto_destino.latitude,
        'Longitud': punto_destino.longitude,
        'Elevacion': punto_destino.elevation
    }

    # Calcula la distancia total considerando todos los puntos intermedios del segmento
    distancia_total = 0
    for track in gpx.tracks:
        for segment in track.segments:
            for i in range(1, len(segment.points)):
                punto_anterior = segment.points[i-1]
                punto_actual = segment.points[i]
                coords_anteriores = (punto_anterior.latitude, punto_anterior.longitude)
                coords_actuales = (punto_actual.latitude, punto_actual.longitude)
                distancia_total += geopy.distance.distance(coords_anteriores, coords_actuales).meters

    return origen, destino, distancia_total

def obtener_nombre_lugar(coordenadas, reintentos=3, timeout=10):
    # Inicializa el geolocalizador con un agente de usuario
    geolocalizador = Nominatim(user_agent="geo_names_app")
    
    for intento in range(reintentos):
        try:
            ubicaciones = geolocalizador.reverse(coordenadas, exactly_one=False, timeout=timeout)
            lugar_cercano = None
            distancia_minima = float('inf')
            
            for ubicacion in ubicaciones:
                lugar = ubicacion.raw['address']
                lat = ubicacion.latitude
                lon = ubicacion.longitude
                distancia = geopy.distance.distance(coordenadas, (lat, lon)).meters
                
                if distancia < distancia_minima:
                    lugar_cercano = lugar
                    distancia_minima = distancia
                    
            if lugar_cercano:
                codigo_pais = lugar_cercano.get('country_code', '').upper()[:3]
                
                nombre_lugar = {
                    'Pais': codigo_pais,
                    'Provincia': lugar_cercano.get('state', ''),
                    'Ciudad': lugar_cercano.get('city', '')
                }
                return nombre_lugar
            else:
                return {'Pais': '', 'Provincia': '', 'Ciudad': ''}
        except geopy.exc.GeocoderTimedOut:
            print(f"Timeout en intento {intento + 1} para coordenadas {coordenadas}. Reintentando...")
            time.sleep(1)  # Espera 1 segundo antes de reintentar
    
    raise Exception(f"No se pudo obtener el nombre del lugar para las coordenadas {coordenadas} después de {reintentos} intentos.")

def limpiar_nombre(nombre):
    # Normaliza el nombre, elimina acentos y espacios
    nombre_limpio = unidecode.unidecode(nombre).strip().replace(" ", "")
    return nombre_limpio

def cambiar_nombre_archivos(ruta_directorio):
    # Obtiene el directorio padre del directorio objetivo
    directorio_padre = os.path.dirname(ruta_directorio)
    # Crea una carpeta nueva con la fecha y hora actual en el nombre
    fecha_hora_actual = datetime.now().strftime('%Y-%m-%d_%H-%M')
    nueva_carpeta = os.path.join(directorio_padre, f"{fecha_hora_actual}-ResultadosAdvanceTrack")
    os.makedirs(nueva_carpeta, exist_ok=True)
    
    # Recorre recursivamente todos los archivos y subdirectorios en el directorio objetivo
    for root, dirs, files in os.walk(ruta_directorio):
        for archivo in files:
            if archivo.endswith('.gpx'):
                ruta_archivo = os.path.join(root, archivo)
                # Intenta obtener los datos de origen y destino del archivo GPX
                try:
                    origen, destino, distancia = obtener_datos_gpx(ruta_archivo)
                except Exception as e:
                    print(f"Error al procesar {archivo}: {e}")
                    continue
                
                try:
                    nombre_origen = obtener_nombre_lugar((origen['Latitud'], origen['Longitud']))
                    nombre_destino = obtener_nombre_lugar((destino['Latitud'], destino['Longitud']))
                except Exception as e:
                    print(f"Error al obtener nombres de lugar para {archivo}: {e}")
                    continue
                
                nombre_pais_origen = nombre_origen['Pais']
                nombre_pais_destino = nombre_destino['Pais']
                
                # Redondea la distancia y la convierte en un string con unidades apropiadas
                if distancia >= 1000:
                    distancia_str = f"{round(distancia / 1000)}Km"
                else:
                    distancia_str = f"{round(distancia)}Ms"
                
                # Genera el nuevo nombre para el archivo
                nuevo_nombre = f"{origen['Fecha-Hora']}_{distancia_str}_ORIG_{nombre_pais_origen}-{limpiar_nombre(nombre_origen['Provincia'])}-{limpiar_nombre(nombre_origen['Ciudad'])}"
                if nombre_destino != nombre_origen:
                    if nombre_pais_destino != '':
                        nuevo_nombre += f"_DEST_{nombre_pais_destino}-{limpiar_nombre(nombre_destino['Provincia'])}-{limpiar_nombre(nombre_destino['Ciudad'])}"
                
                # Agrega el nombre del creador al nuevo nombre del archivo
                nuevo_nombre += f"_{limpiar_nombre(origen['Creador'])}"
                
                nuevo_nombre += ".gpx"
                
                # Copia el archivo a la nueva carpeta con el nuevo nombre
                ruta_nuevo_nombre = os.path.join(nueva_carpeta, nuevo_nombre)
                shutil.copy(ruta_archivo, ruta_nuevo_nombre)
                print(f"Archivo copiado: {archivo} -> {nuevo_nombre}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cambiar nombres de archivos GPX.')
    parser.add_argument('directorio', type=str, help='Ruta del directorio que contiene los archivos GPX')

    args = parser.parse_args()

    cambiar_nombre_archivos(args.directorio)
