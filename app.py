import os
import base64
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify
from datetime import datetime

# Substitua este código pelo seu código de acesso ao Google Sheets
def setup_google_sheets(json_credentials_content):
    try:
        creds = Credentials.from_service_account_info(
            info=json_credentials_content,
            scopes=['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"Erro ao autenticar: {e}")
        return None

def write_to_sheet(client, sheet_title, data):
    try:
        sheet = client.open(sheet_title).sheet1
        sheet.append_row(data)
        print(f"Dados gravados com sucesso em '{sheet_title}'.")
        return True
    except Exception as e:
        print(f"Erro ao gravar na folha de cálculo: {e}")
        return False

# ----- Código do Servidor Flask -----
app = Flask(__name__)

# Configuração para o CORS (necessário para aceitar requisições do navegador)
from flask_cors import CORS
CORS(app)

@app.route('/upload', methods=['POST'])
def upload_data():
    data = request.json
    
    # 1. Extrair os dados da requisição
    photo_data_url = data.get('photo')
    coords = data.get('coords')

    if not photo_data_url or not coords:
        return jsonify({"message": "Dados incompletos"}), 400

    # 2. Processar a foto e as coordenadas
    latitude = coords.get('latitude')
    longitude = coords.get('longitude')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # # Salva a foto (opcional, pode ser adaptado)
    # photo_base64 = photo_data_url.split(',')[1]
    # photo_bytes = base64.b64decode(photo_base64)
    # file_path = f"photos/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
    # os.makedirs('photos', exist_ok=True)
    # with open(file_path, 'wb') as f:
    #     f.write(photo_bytes)
    #     print(f"Foto salva em: {file_path}")

    # 3. Gravar no Google Sheets
    sheets_client = setup_google_sheets(os.environ.get('GSPREAD_CREDENTIALS'))
    if sheets_client:
        data_to_write = [timestamp, latitude, longitude]
        if write_to_sheet(sheets_client, "Registo de Fotos", data_to_write):
            return jsonify({"message": "Dados gravados com sucesso!"}), 200
        else:
            return jsonify({"message": "Erro ao gravar dados no Google Sheets"}), 500
    
    return jsonify({"message": "Erro de autenticação com o Google Sheets"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
    
    """
    como colocar num arquivo docker file e correre no render cloud


A sua pergunta aborda um cenário de implementação que é muito comum, mas que exige uma mudança de perspetiva, especialmente no que diz respeito ao Docker e a serviços de nuvem como o Render.

O Problema Fundamental
O seu programa Python para tirar fotos e aceder à câmara não pode ser executado diretamente no Render.

Docker e Contêineres: Um contêiner Docker é um ambiente isolado. Por padrão, ele não tem acesso ao hardware da máquina onde está a correr, como a sua câmara (/dev/video0).

Render Cloud: O Render é um serviço de nuvem. O seu contêiner irá correr num servidor virtual remoto, a milhares de quilómetros da sua máquina. Por isso, é impossível que ele aceda à sua câmara ou ao seu GPS.

A Solução Correta: Uma Arquitetura Cliente-Servidor
O modelo certo para este problema é dividir o seu programa em duas partes:

O Cliente (no navegador do utilizador): Um código HTML e JavaScript (como no exemplo que lhe dei anteriormente) que é executado no seu laptop ou telemóvel. Ele é responsável por tirar a foto e obter as coordenadas de geolocalização.

O Servidor (Python no Docker e Render): Uma aplicação Python que é executada no Render. Ele é responsável por receber a foto e as coordenadas, e depois gravá-las no Google Sheets.

A seguir, explico como construir o servidor Python e o Dockerfile para o Render.

Passo 1: Criar o Servidor Python (API)
Vamos usar o Flask para criar uma API simples que recebe os dados do navegador.

Crie um arquivo chamado app.py:
    
    Nota Importante sobre as Credenciais: No código acima, o setup_google_sheets lê as credenciais de uma variável de ambiente chamada GSPREAD_CREDENTIALS. Isto é a prática segura para o Docker e o Render, pois evita que o arquivo JSON de credenciais seja incluído na imagem.
    """