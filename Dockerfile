# Usa uma imagem base Python leve
FROM python:3.9-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Copia o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements_for_render.txt requirements.txt

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação para o contêiner
COPY . .

# Expõe a porta que o Flask vai usar (5000 por padrão)
EXPOSE 5000

# Comando para iniciar a aplicação
# Usa Gunicorn ou Waitress para produção. Para este exemplo, o Flask é suficiente.
CMD ["flask", "run", "--host=0.0.0.0"]