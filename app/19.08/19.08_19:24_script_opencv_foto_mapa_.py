#touch app/19.08/19.08_19:24_script_opencv_foto_mapa_.py
import cv2
import folium
import os
import datetime
import random # Usado para simular coordenadas de GPS

# Tente 1 ou 2 se 0 não funcionar
camera = cv2.VideoCapture(1)
if not camera.isOpened():#camera = cv2.VideoCapture(0) para camera = cv2.VideoCapture(2) try solve can't open camera by index
    camera = cv2.VideoCapture(2)  # Tenta a câmara padrão se a 1 não estiver disponível ou falhar   
def take_photo_with_geo(output_folder):
    """
    Tira uma foto usando a câmara e associa coordenadas de geolocalização.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 1. Obter geolocalização (Simulado)
    # Na vida real, você usaria uma biblioteca de GPS para obter coordenadas
    # Ex: lat, lon = get_real_gps_coordinates()
    # Para este exemplo, vamos gerar coordenadas aleatórias perto de Lisboa, Portugal
    latitude = random.uniform(38.7, 38.8)
    longitude = random.uniform(-9.2, -9.1)
    
    print(f"Coordenadas de geolocalização obtidas: Lat: {latitude:.4f}, Lon: {longitude:.4f}")

    # 2. Capturar a imagem
    camera = cv2.VideoCapture(2) # '0' refere-se à primeira câmara
    if not camera.isOpened():
        print("Erro: Não foi possível aceder à câmara.")
        return None, None

    # Tira a foto
    ret, frame = camera.read()
    camera.release()
    
    if not ret:
        print("Erro: Não foi possível capturar o frame da câmara.")
        return None, None
        
    # Gera um nome de arquivo único com a data e hora
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"photo_{timestamp}.jpg"
    file_path = os.path.join(output_folder, file_name)

    # Salva a imagem
    cv2.imwrite(file_path, frame)
    print(f"Foto salva em: {file_path}")

    return (latitude, longitude), file_path

def create_map_with_photo(photo_coords, photo_path, output_filename='mapa_da_foto.html'):
    """
    Cria um mapa interativo com um marcador na localização da foto.
    """
    # Cria o mapa centrado na localização da foto
    photo_map = folium.Map(location=photo_coords, zoom_start=15)

    # Adiciona um marcador no local da foto
    # Usa a foto salva como o ícone
    icon_html = f"""
    <img src="data:image/jpeg;base64,{base64.b64encode(open(photo_path, "rb").read()).decode('utf-8')}" width="100">
    """
    popup_html = f"<b>Sua foto</b><br>Tirada em: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>Lat: {photo_coords[0]:.4f}<br>Lon: {photo_coords[1]:.4f}"
    
    folium.Marker(
        location=photo_coords,
        popup=folium.Popup(popup_html, max_width=300),
        tooltip="Sua foto",
        icon=folium.Icon(icon='camera', color='red')
    ).add_to(photo_map)
    
    # Salva o mapa em um arquivo HTML
    photo_map.save(output_filename)
    print(f"\nMapa gerado com sucesso e salvo como '{output_filename}'.")
    print("Abra este arquivo em seu navegador para visualizar a localização da foto.")

# --- Execução do Programa ---
if __name__ == "__main__":
    import base64
    photos_folder = './fotos_capturadas'
    
    # 1. Tira a foto e obtém as coordenadas
    coords, saved_photo_path = take_photo_with_geo(photos_folder)
    
    # 2. Se a foto e as coordenadas foram obtidas com sucesso, cria o mapa
    if coords and saved_photo_path:
        create_map_with_photo(coords, saved_photo_path)