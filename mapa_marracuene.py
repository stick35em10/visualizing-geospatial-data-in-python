import geopandas as gpd
import folium
from folium import GeoJson
import json

# 1. Dados dos Postos Administrativos de Marracuene
# NOTA: Estas coordenadas são de exemplo e não representam os limites oficiais.
# Elas são criadas para demonstrar a funcionalidade.
marracuene_data = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "Posto Administrativo de Marracuene",
                "color": "#1f77b4"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [32.61, -25.82], [32.65, -25.82], [32.65, -25.78], [32.61, -25.78], [32.61, -25.82]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {
                "name": "Posto Administrativo de Machubo",
                "color": "#ff7f0e"
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [32.70, -25.78], [32.74, -25.78], [32.74, -25.74], [32.70, -25.74], [32.70, -25.78]
                ]]
            }
        }
    ]
}

# 2. Carregar os dados dos pontos de água do arquivo GeoJSON
try:
    with open('data/export.geojson', 'r') as f:
        water_points_data = json.load(f)
except FileNotFoundError:
    print("Erro: O arquivo 'export.geojson' não foi encontrado. Por favor, certifique-se de que está no mesmo diretório do script.")
    exit()

# 3. Criar o mapa interativo
# Coordenadas do centro de Marracuene para o mapa
m = folium.Map(location=[-25.8, 32.65], zoom_start=11, tiles="CartoDB positron")

# 4. Adicionar a camada dos Postos Administrativos ao mapa
for feature in marracuene_data['features']:
    GeoJson(
        feature,
        name=feature['properties']['name'],
        tooltip=feature['properties']['name'],
        style_function=lambda x: {
            'fillColor': x['properties']['color'],
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.5
        }
    ).add_to(m)

# 5. Adicionar a camada dos pontos de água ao mapa
# Iterar sobre as features do GeoJSON
for feature in water_points_data['features']:
    # Verificar se a feature é um ponto
    if feature['geometry']['type'] == 'Point':
        # Obter as coordenadas (longitude, latitude)
        lon, lat = feature['geometry']['coordinates']
        
        # Obter as propriedades para a janela pop-up
        properties = feature['properties']
        popup_html = "<h4>Ponto de Água</h4>"
        for key, value in properties.items():
            popup_html += f"<b>{key}:</b> {value}<br>"
        
        # Adicionar o marcador ao mapa
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=properties.get('name', 'Ponto de Água')
        ).add_to(m)

# 6. Salvar o mapa em um arquivo HTML
output_file = 'mapa_marracuene.html'
m.save(output_file)

print(f"Mapa salvo com sucesso em '{output_file}'.")
print("Abra este arquivo no seu navegador para visualizar o mapa interativo.")

