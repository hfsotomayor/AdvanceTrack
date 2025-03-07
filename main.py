import os
import gpxpy
import argparse
import geopy.distance
from geopy.geocoders import Nominatim
import unidecode
import time
import shutil
from datetime import datetime
import xml.etree.ElementTree as ET  # Para manejar archivos .tcx

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

def obtener_datos_tcx(archivo_tcx):
    # Abre y parsea el archivo TCX
    tree = ET.parse(archivo_tcx)
    root = tree.getroot()
    
    ns = {'tcx': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
    # Encuentra todos los puntos del track
    trackpoints = root.findall('.//tcx:Trackpoint', ns)
    
    if not trackpoints:
        raise ValueError("El archivo TCX no contiene puntos válidos")
    
    # Extrae el primer punto del track
    punto_origen = trackpoints[0]
    lat_origen = float(punto_origen.find('tcx:Position/tcx:LatitudeDegrees', ns).text)
    lon_origen = float(punto_origen.find('tcx:Position/tcx:LongitudeDegrees', ns).text)
    ele_origen = float(punto_origen.find('tcx:AltitudeMeters', ns).text)
    tiempo_origen = punto_origen.find('tcx:Time', ns).text
    fecha_hora_origen = datetime.strptime(tiempo_origen, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d_%H-%M')
    
    origen = {
        'Fecha-Hora': fecha_hora_origen,
        'Latitud': lat_origen,
        'Longitud': lon_origen,
        'Elevacion': ele_origen,
        'Creador': root.find('.//tcx:Author/tcx:Name', ns).text if root.find('.//tcx:Author/tcx:Name', ns) is not None else 'Desconocido'
    }
    
    # Extrae el último punto del track
    punto_destino = trackpoints[-1]
    lat_destino = float(punto_destino.find('tcx:Position/tcx:LatitudeDegrees', ns).text)
    lon_destino = float(punto_destino.find('tcx:Position/tcx:LongitudeDegrees', ns).text)
    ele_destino = float(punto_destino.find('tcx:AltitudeMeters', ns).text)
    
    destino = {
        'Latitud': lat_destino,
        'Longitud': lon_destino,
        'Elevacion': ele_destino
    }
    
    # Calcula la distancia total considerando todos los puntos intermedios del track
    distancia_total = 0
    for i in range(1, len(trackpoints)):
        punto_anterior = trackpoints[i-1]
        punto_actual = trackpoints[i]
        coords_anteriores = (float(punto_anterior.find('tcx:Position/tcx:LatitudeDegrees', ns).text), float(punto_anterior.find('tcx:Position/tcx:LongitudeDegrees', ns).text))
        coords_actuales = (float(punto_actual.find('tcx:Position/tcx:LatitudeDegrees', ns).text), float(punto_actual.find('tcx:Position/tcx:LongitudeDegrees', ns).text))
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
            if archivo.endswith('.gpx') or archivo.endswith('.tcx'):
                ruta_archivo = os.path.join(root, archivo)
                # Intenta obtener los datos de origen y destino del archivo GPX o TCX
                try:
                    if archivo.endswith('.gpx'):
                        origen, destino, distancia = obtener_datos_gpx(ruta_archivo)
                    else:
                        origen, destino, distancia = obtener_datos_tcx(ruta_archivo)
                except Exception as e:
                    print(f"Error al procesar {archivo}: {e}")
                   
