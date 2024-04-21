import os
import gpxpy
import argparse
import geopy.distance
from geopy.geocoders import Nominatim
import unidecode

def obtener_datos_gpx(archivo_gpx):
    with open(archivo_gpx, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

    punto_origen = gpx.tracks[0].segments[0].points[0]
    origen = {
        'Fecha-Hora': punto_origen.time.strftime('%Y-%m-%d_%H-%M'),
        'Pais': punto_origen.latitude,
        'Provincia': punto_origen.longitude,
        'Ciudad': punto_origen.elevation
    }

    punto_destino = gpx.tracks[0].segments[-1].points[-1]
    destino = {
        'Pais': punto_destino.latitude,
        'Provincia': punto_destino.longitude,
        'Ciudad': punto_destino.elevation
    }

    return origen, destino

def obtener_nombre_lugar(coordenadas):
    geolocalizador = Nominatim(user_agent="geo_names_app")
    ubicaciones = geolocalizador.reverse(coordenadas, exactly_one=False)
    
    lugar_cercano = None
    distancia_minima = float('inf')
    
    for ubicacion in ubicaciones:
        lugar = ubicacion.raw['address']
        distancia = geopy.distance.distance(coordenadas, (ubicacion.latitude, ubicacion.longitude)).meters
        
        if distancia < distancia_minima:
            lugar_cercano = lugar
            distancia_minima = distancia
            
    if lugar_cercano:
        codigo_pais = ubicacion.raw['address'].get('country_code', '').upper()[:3]
        
        nombre_lugar = {
            'Pais': codigo_pais,
            'Provincia': lugar_cercano.get('state', ''),
            'Ciudad': lugar_cercano.get('city', '')
        }
        return nombre_lugar
    else:
        return {'Pais': '', 'Provincia': '', 'Ciudad': ''}

def limpiar_nombre(nombre):
    nombre_limpio = unidecode.unidecode(nombre).strip().replace(" ", "")
    return nombre_limpio

def cambiar_nombre_archivos(ruta_directorio):
    archivos = os.listdir(ruta_directorio)
    
    for archivo in archivos:
        if archivo.endswith('.gpx'):
            origen, destino = obtener_datos_gpx(os.path.join(ruta_directorio, archivo))
            nombre_origen = obtener_nombre_lugar((origen['Pais'], origen['Provincia']))
            nombre_destino = obtener_nombre_lugar((destino['Pais'], destino['Provincia']))
            
            nombre_pais_origen = nombre_origen['Pais']
            nombre_pais_destino = nombre_destino['Pais']
            
            if nombre_destino != nombre_origen:
                nuevo_nombre = f"{origen['Fecha-Hora']}_ORIG_{nombre_pais_origen}-{limpiar_nombre(nombre_origen['Provincia'])}-{limpiar_nombre(nombre_origen['Ciudad'])}"
                if nombre_pais_destino != '':
                    nuevo_nombre += f"_DEST_{nombre_pais_destino}-{limpiar_nombre(nombre_destino['Provincia'])}-{limpiar_nombre(nombre_destino['Ciudad'])}"
            else:
                nuevo_nombre = f"{origen['Fecha-Hora']}_ORIG_{nombre_pais_origen}-{limpiar_nombre(nombre_origen['Provincia'])}-{limpiar_nombre(nombre_origen['Ciudad'])}"
            
            nuevo_nombre += ".gpx"
            
            os.rename(os.path.join(ruta_directorio, archivo), os.path.join(ruta_directorio, nuevo_nombre))
            print(f"Archivo renombrado: {archivo} -> {nuevo_nombre}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cambiar nombres de archivos GPX.')
    parser.add_argument('directorio', type=str, help='Ruta del directorio que contiene los archivos GPX')

    args = parser.parse_args()

    cambiar_nombre_archivos(args.directorio)
