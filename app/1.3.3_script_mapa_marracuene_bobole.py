import folium

# Coordenadas aproximadas (latitude, longitude)
locais = [
    {"nome": "Marracuene - Sede (Fontanário)", "coords": (-25.703, 32.676), "tipo": "Fontanário Público"},
    {"nome": "Mahubo (Reservatório)", "coords": (-25.750, 32.720), "tipo": "Reservatório"},
    {"nome": "Bobole (Furo Comunitário)", "coords": (-25.830, 32.580), "tipo": "Furo / Poço"},
    {"nome": "Estrada Marracuene–Macaneta (Ponto de Água)", "coords": (-25.690, 32.610), "tipo": "Fontanário Informal"}
]

# Criar mapa centralizado em Marracuene
mapa = folium.Map(location=[-25.73, 32.65], zoom_start=11)

# Adicionar pontos ao mapa
for local in locais:
    folium.Marker(
        location=local["coords"],
        popup=f"{local['nome']} ({local['tipo']})",
        tooltip=local["nome"],
        icon=folium.Icon(color="blue", icon="tint", prefix="fa")
    ).add_to(mapa)

# Guardar o mapa em HTML
mapa.save("mapa_marracuene_bobole.html")

print("✅ Mapa criado: abra o ficheiro mapa_marracuene_bobole.html no navegador.")